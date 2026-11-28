use crewden_desktop::config::{DesktopCliOptions, DesktopPaths};
use crewden_desktop::host_server::{start_host_server, RunningHostServer};
use crewden_desktop::notifications::NoopUiBridge;
use reqwest::{Method, RequestBuilder, StatusCode};
use serde_json::{json, Value};
use std::{sync::Arc, time::Duration};
use tempfile::TempDir;
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tokio::time::timeout;

const ATTACHMENT: &str = "/im/v1/conversations/c1/attachments/file1";
const LOGIN: &str = "/im/v1/auth/login";
const WAIT: Duration = Duration::from_secs(5);

struct Fixture {
    _root: TempDir,
    upstream: TcpListener,
    host: RunningHostServer,
}

impl Fixture {
    async fn start() -> Self {
        let upstream = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
        let root = tempfile::tempdir().unwrap();
        let paths = DesktopPaths::resolve(&DesktopCliOptions {
            isolated_root: Some(root.path().to_owned()),
            ..Default::default()
        })
        .unwrap();
        let origin = format!("http://{}", upstream.local_addr().unwrap());
        let host = start_host_server(
            paths,
            Some(&origin),
            None,
            Arc::new(NoopUiBridge::default()),
        )
        .await
        .unwrap();
        Self {
            _root: root,
            upstream,
            host,
        }
    }

    fn request(&self, method: Method, path: &str) -> RequestBuilder {
        reqwest::Client::new()
            .request(method, format!("http://127.0.0.1:{}{path}", self.host.port))
            .header(
                "cookie",
                format!("__crewden_desktop_cap={}", self.host.state.cap_token),
            )
            .bearer_auth("test-member")
            .timeout(WAIT)
    }

    // A raw upstream socket lets the fixture stop after valid headers and part of a chunked body.
    async fn accept(&self, method: &str, path: &str) -> TcpStream {
        loop {
            let (mut socket, _) = timeout(WAIT, self.upstream.accept())
                .await
                .expect("proxy must contact IM")
                .unwrap();
            let mut reader = BufReader::new(&mut socket);
            let mut request_line = String::new();
            reader.read_line(&mut request_line).await.unwrap();
            let mut headers = String::new();
            let mut line = String::new();
            loop {
                line.clear();
                assert!(reader.read_line(&mut line).await.unwrap() > 0);
                if line == "\r\n" {
                    break;
                }
                headers.push_str(&line.to_ascii_lowercase());
            }
            // A signed-in host also refreshes in the background. Keep the session without syncing a badge.
            if request_line == "POST /im/v1/auth/refresh HTTP/1.1\r\n" {
                socket.write_all(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").await.unwrap();
                continue;
            }
            assert_eq!(request_line, format!("{method} {path} HTTP/1.1\r\n"));
            if path != LOGIN {
                assert!(headers.contains("authorization: bearer test-member\r\n"));
            }
            return socket;
        }
    }

    async fn login(&self) {
        let request = tokio::spawn(
            self.request(Method::POST, LOGIN)
                .json(&json!({ "username": "member", "password": "fixture" }))
                .send(),
        );
        let mut socket = self.accept("POST", LOGIN).await;
        let session = json!({
            "access_token": "test-member",
            "refresh_token": "test-refresh",
            "user": { "id": "member", "owner_id": "member", "username": "member" }
        })
        .to_string();
        let reply = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{session}",
            session.len()
        );
        socket.write_all(reply.as_bytes()).await.unwrap();
        let response = request.await.unwrap().unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(
            response.json::<Value>().await.unwrap()["access_token"],
            "test-member"
        );
    }
}

#[tokio::test]
async fn complete_download_preserves_file_and_metadata() {
    let fixture = Fixture::start().await;
    let download = tokio::spawn(fixture.request(Method::GET, ATTACHMENT).send());
    let mut socket = fixture.accept("GET", ATTACHMENT).await;
    socket.write_all(b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename=test.bin\r\nContent-Length: 4\r\n\r\n\0\x01\x80\xff").await.unwrap();
    let response = download.await.unwrap().unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(
        response.headers()["content-type"],
        "application/octet-stream"
    );
    assert_eq!(
        response.headers()["content-disposition"],
        "attachment; filename=test.bin"
    );
    assert_eq!(response.content_length(), Some(4));
    assert_eq!(&response.bytes().await.unwrap()[..], b"\0\x01\x80\xff");
}

#[tokio::test]
async fn interrupted_chunked_download_fails() {
    let fixture = Fixture::start().await;
    let download = tokio::spawn(fixture.request(Method::GET, ATTACHMENT).send());
    let mut socket = fixture.accept("GET", ATTACHMENT).await;
    socket
        .write_all(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4\r\npart\r\n")
        .await
        .unwrap();
    let mut response = download.await.unwrap().unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(&response.chunk().await.unwrap().unwrap()[..], b"part");
    socket.shutdown().await.unwrap();
    assert!(
        response.bytes().await.is_err(),
        "incomplete attachment returned a complete body"
    );
}

#[tokio::test]
async fn slow_preview_can_cancel_before_upstream_finishes() {
    let fixture = Fixture::start().await;
    let download = tokio::spawn(fixture.request(Method::GET, ATTACHMENT).send());
    let mut socket = fixture.accept("GET", ATTACHMENT).await;
    const PREFIX: usize = 512 * 1024 + 1;
    socket
        .write_all(
            format!("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n{PREFIX:x}\r\n")
                .as_bytes(),
        )
        .await
        .unwrap();
    socket.write_all(&vec![b'a'; PREFIX]).await.unwrap();
    socket.write_all(b"\r\n").await.unwrap();

    let mut response = download
        .await
        .unwrap()
        .expect("preview must receive headers before EOF");
    let mut received = 0;
    while received < PREFIX {
        received += response.chunk().await.unwrap().unwrap().len();
    }
    drop(response);
    let mut byte = [0];
    let read = timeout(WAIT, socket.read(&mut byte))
        .await
        .expect("cancel must reach IM");
    match read {
        Ok(n) => assert_eq!(n, 0),
        Err(e) => assert_eq!(e.kind(), std::io::ErrorKind::ConnectionReset),
    }
}

#[tokio::test]
async fn conversation_write_updates_badge_only_after_complete_response() {
    let fixture = Fixture::start().await;
    fixture.login().await;
    let path = "/im/v1/conversations/c1";
    for (body, missing, expected) in [
        (r#"{"id":"c1","unread_count":3}"#, 0, StatusCode::OK),
        (
            r#"{"id":"c1","unread_count":9}"#,
            1,
            StatusCode::BAD_GATEWAY,
        ),
    ] {
        let request = tokio::spawn(fixture.request(Method::PATCH, path).send());
        let mut socket = fixture.accept("PATCH", path).await;
        let declared = body.len() + missing;
        socket
            .write_all(
                format!("HTTP/1.1 200 OK\r\nContent-Length: {declared}\r\n\r\n{body}").as_bytes(),
            )
            .await
            .unwrap();
        socket.shutdown().await.unwrap();
        let response = request.await.unwrap().unwrap();
        assert_eq!(response.status(), expected);
        if expected == StatusCode::OK {
            assert_eq!(response.text().await.unwrap(), body);
        }
        assert_eq!(fixture.host.state.notification_center.unread(), 3);
    }
}
