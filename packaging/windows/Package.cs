using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

internal static class Package {
    internal static readonly string Home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Crewden");
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    internal const string Setup = "Crewden-Setup-x64.exe";
    const string Repository = "https://github.com/Mrchen116/nano-multiagent/releases/download/";

    internal static void PrivateRoot() {
        var acl = new DirectorySecurity();
        var user = WindowsIdentity.GetCurrent().User;
        acl.SetAccessRuleProtection(true, false);
        acl.AddAccessRule(new FileSystemAccessRule(user, FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
        Directory.CreateDirectory(Home, acl);
    }
    internal static void Check(bool valid, string message) {
        if (!valid) throw new InvalidDataException(message);
    }
    internal static bool Digest(string value) {
        return value != null && Regex.IsMatch(value, @"\A[a-f0-9]{64}\z");
    }
    internal static string Hash(string file) {
        using (var sha = SHA256.Create())
        using (var stream = File.OpenRead(file))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
    internal static string Origin(string raw) {
        Uri url;
        Check(Uri.TryCreate(raw, UriKind.Absolute, out url) && url.Scheme == "https" &&
            url.Host.Length != 0 && url.UserInfo == "" && url.Query == "" && url.Fragment == "" &&
            (raw == url.GetLeftPart(UriPartial.Authority) || raw == url.GetLeftPart(UriPartial.Authority) + "/"),
            "连接地址必须是完整的 HTTPS 站点地址。");
        return url.GetLeftPart(UriPartial.Authority);
    }
    // IM metadata must come directly from the confirmed origin. Only fixed GitHub assets may redirect.
    static void Fetch(string address, Stream output, long limit, bool asset, Action<long> progress = null) {
        var uri = new Uri(address);
        for (int hops = 0; hops < 5; hops++) {
            var request = (HttpWebRequest)WebRequest.Create(uri);
            request.AllowAutoRedirect = false;
            request.Timeout = 45000;
            request.ReadWriteTimeout = 45000;
            request.UserAgent = "Crewden-Windows/1";
            using (var response = (HttpWebResponse)request.GetResponse()) {
                if ((int)response.StatusCode >= 300 && (int)response.StatusCode < 400) {
                    var next = new Uri(uri, response.Headers[HttpResponseHeader.Location]);
                    Check(asset && next.Scheme == "https" && next.IsDefaultPort && next.UserInfo == "" &&
                        (next.Host == "release-assets.githubusercontent.com" || next.Host == "objects.githubusercontent.com"),
                        "下载重定向到了不受支持的站点。");
                    uri = next;
                    continue;
                }
                Check(response.StatusCode == HttpStatusCode.OK && response.ContentLength <= limit, "下载大小或状态无效。");
                using (var source = response.GetResponseStream()) {
                    byte[] buffer = new byte[81920];
                    int count;
                    long total = 0;
                    long nextUpdate = 0;
                    while ((count = source.Read(buffer, 0, buffer.Length)) > 0) {
                        total += count;
                        Check(total <= limit, "下载内容超过固定大小。");
                        output.Write(buffer, 0, count);
                        if (progress != null && (total >= nextUpdate || total == limit)) {
                            progress(total);
                            nextUpdate = total + 1024 * 1024;
                        }
                    }
                }
                return;
            }
        }
        throw new IOException("下载重定向次数过多。");
    }
    internal sealed class Asset {
        public string name { get; set; }
        public string download_url { get; set; }
        public string sha256 { get; set; }
        public long size { get; set; }
        internal void Validate() {
            Check(Digest(sha256) && size > 0, "发行文件缺少有效大小或 SHA-256。");
        }
    }
    internal sealed class Release {
        public string version { get; set; }
        public string source_commit { get; set; }
        public int updater_protocol { get; set; }
        public int data_epoch { get; set; }
        public int launcher_protocol { get; set; }
        public int node_major { get; set; }
        public string pnpm_version { get; set; }
        public string platform { get; set; }
        public string package { get; set; }
        public string sha256 { get; set; }
        public string download_url { get; set; }
        public long size { get; set; }
        public Asset installer { get; set; }
        public Asset runtime { get; set; }
        public Asset app { get; set; }
        internal string Base;
        internal string Raw;
    }
    internal static Release Manifest(string origin) {
        string raw;
        using (var data = new MemoryStream()) {
            Fetch(Origin(origin) + "/install/manifest.win32-x64.json", data, 128 * 1024, false);
            raw = Encoding.UTF8.GetString(data.ToArray());
        }
        var m = Json.Deserialize<Release>(raw);
        Check(m != null && m.platform == "win32-x64" && m.package == "windows-x64.json" &&
            m.updater_protocol == 1 && m.data_epoch == 1 && m.node_major == 24 && m.pnpm_version == "11.7.0" &&
            m.source_commit != null && Regex.IsMatch(m.source_commit, @"\A[0-9a-f]{40}\z") &&
            Digest(m.sha256) && m.size > 0 && m.size <= 128 * 1024 && m.installer != null, "此 IM 没有兼容的 Windows 发行版本。");
        var tag = m.version == m.source_commit ? "node-" + m.source_commit : "v" + m.version;
        Check(m.version == m.source_commit || (m.version != null && Regex.IsMatch(m.version,
            @"\A(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\z")), "发行版本格式无效。");
        m.Base = Repository + tag + "/";
        m.Raw = raw;
        m.installer.Validate();
        Check(m.download_url == m.Base + m.package && m.installer.download_url == m.Base + Setup,
            "发行地址不匹配，请从原网页重新下载。");
        return m;
    }
    static void Download(string file, string url, long size, string sha, Action<long> progress = null) {
        using (var stream = new FileStream(file, FileMode.CreateNew)) {
            Fetch(url, stream, size, true, progress);
            stream.Flush(true);
        }
        Check(new FileInfo(file).Length == size && Hash(file) == sha, "下载文件校验失败，请重试。");
    }
    // Framework ZIP extraction otherwise hits MAX_PATH on ordinary Windows 10 configurations.
    // Keep normal paths for launching processes and use the extended form only for filesystem I/O.
    static string ExtendedPath(string path) {
        if (path.StartsWith(@"\\?\")) return path;
        var absolute = Path.GetFullPath(path);
        return absolute.StartsWith(@"\\") ? @"\\?\UNC\" + absolute.Substring(2) : @"\\?\" + absolute;
    }
    static void Extract(string zipPath, string destination) {
        using (var zip = ZipFile.OpenRead(zipPath)) {
            foreach (var entry in zip.Entries) {
                string relative = entry.FullName;
                foreach (var segment in relative.Split('/'))
                    Check(segment.Length != 0 && segment != "." && segment != ".." &&
                        segment.IndexOfAny(Path.GetInvalidFileNameChars()) == -1 && !segment.EndsWith(".") && !segment.EndsWith(" ") &&
                        !Regex.IsMatch(segment, @"\A(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)", RegexOptions.IgnoreCase),
                        "发行包中包含无效的 Windows 文件名。");
                var type = (entry.ExternalAttributes >> 16) & 0xF000;
                Check((type == 0 || type == 0x8000) && (entry.ExternalAttributes & 0x400) == 0,
                    "发行包中仅允许普通文件。");
                var path = Path.Combine(destination, relative.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(ExtendedPath(Path.GetDirectoryName(path)));
                entry.ExtractToFile(ExtendedPath(path), false);
            }
        }
    }
    static string Cache(Asset asset, string remote, string temp, bool runtime, Action<string> report) {
        var final = Path.Combine(Home, "cache", asset.sha256);
        if (File.Exists(Path.Combine(final, ".complete")) &&
            File.Exists(Path.Combine(final, runtime ? "node.exe" : "apps/node/lib/cli.js"))) return final;
        report(runtime ? "正在准备运行环境。首次下载可能需要几分钟…" : "正在准备 Crewden 应用…");
        var zip = Path.Combine(temp, asset.name);
        string label = runtime ? "运行环境" : "Crewden 应用";
        Download(zip, remote + asset.name, asset.size, asset.sha256, received =>
            report(String.Format("正在下载{0}：{1:F1} / {2:F1} MiB", label, received / 1048576.0, asset.size / 1048576.0)));
        report("正在安装" + label + "…");
        var stage = Path.Combine(temp, runtime ? "runtime" : "app");
        Directory.CreateDirectory(stage);
        Extract(zip, stage);
        if (runtime) Launcher.Run(Path.Combine(stage, "node.exe"), Path.Combine(stage, "layout.mjs"), "runtime", stage, final);
        File.WriteAllText(Path.Combine(stage, ".complete"), asset.sha256);
        Directory.Move(stage, final);
        return final;
    }
    internal static string Prepare(Release m, Action<string> report) {
        PrivateRoot();
        var version = Path.Combine(Home, "versions", m.sha256);
        using (var mutex = new Mutex(false, @"Local\CrewdenPrepare-" + WindowsIdentity.GetCurrent().User.Value)) {
            try { if (!mutex.WaitOne(TimeSpan.FromMinutes(15))) throw new IOException("其他安装正在运行，请稍后重试。"); }
            catch (AbandonedMutexException) { }
            try {
                if (File.Exists(Path.Combine(version, ".ready")) && File.Exists(Path.Combine(version, "runtime", "node.exe")) &&
                    File.Exists(Path.Combine(version, "apps/node/lib/cli.js"))) return version;
                Directory.CreateDirectory(Path.GetDirectoryName(version));
                Directory.CreateDirectory(Path.Combine(Home, "cache"));
                // Cancellation or power loss can skip finally. This mutex owns all preparation stages.
                foreach (string left in Directory.GetDirectories(Home, "stage-*")) {
                    if (Regex.IsMatch(Path.GetFileName(left), @"\Astage-[0-9a-f]{32}\z") &&
                        (File.GetAttributes(left) & FileAttributes.ReparsePoint) == 0) RemoveTree(left);
                }
                var temp = Directory.CreateDirectory(Path.Combine(Home, "stage-" + Guid.NewGuid().ToString("N"))).FullName;
                try {
                    string descriptor = Path.Combine(temp, m.package);
                    Download(descriptor, m.download_url, m.size, m.sha256);
                    var d = Json.Deserialize<Release>(File.ReadAllText(descriptor));
                    Check(d != null && d.version == m.version && d.source_commit == m.source_commit &&
                        d.updater_protocol == 1 && d.data_epoch == 1 && d.launcher_protocol == 1 &&
                        d.runtime != null && d.runtime.name == "windows-runtime-x64.zip" &&
                        d.app != null && d.app.name == "windows-app-x64.zip", "此版本需要另一个启动器，请从原网页重新下载。");
                    d.runtime.Validate();
                    d.app.Validate();
                    var runtime = Cache(d.runtime, m.Base, temp, true, report);
                    var app = Cache(d.app, m.Base, temp, false, report);
                    var metadata = Json.Deserialize<Release>(File.ReadAllText(Path.Combine(app, ".nano-release.json")));
                    Check(metadata != null && metadata.source_commit == m.source_commit &&
                        metadata.updater_protocol == m.updater_protocol && metadata.data_epoch == m.data_epoch,
                        "应用归档的源码或协议与版本描述不一致。");
                    var stage = Directory.CreateDirectory(Path.Combine(temp, "version")).FullName;
                    var node = Path.Combine(runtime, "node.exe");
                    var layout = Path.Combine(runtime, "layout.mjs");
                    Launcher.Run(node, layout, "version", stage, version, runtime, app);
                    File.WriteAllText(Path.Combine(stage, ".release-manifest.json"), m.Raw, new UTF8Encoding(false));
                    File.Copy(descriptor, Path.Combine(stage, m.package));
                    if (Directory.Exists(version)) RemoveTree(version);
                    Directory.Move(stage, version);
                    Launcher.Run(node, layout, "verify", version);
                    File.WriteAllText(Path.Combine(version, ".ready"), m.sha256);
                    return version;
                } finally { RemoveTree(temp); }
            } finally { mutex.ReleaseMutex(); }
        }
    }
    // Never recurse into junctions. A partially prepared version points at shared healthy caches.
    static void RemoveTree(string directory) {
        directory = ExtendedPath(directory);
        foreach (string child in Directory.GetDirectories(directory)) {
            if ((File.GetAttributes(child) & FileAttributes.ReparsePoint) != 0) Directory.Delete(child);
            else RemoveTree(child);
        }
        foreach (string file in Directory.GetFiles(directory)) File.Delete(file);
        Directory.Delete(directory);
    }
}
