using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;

internal static class Launcher {
    static readonly string Self = Assembly.GetExecutingAssembly().Location;
    static readonly string Shortcut = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Crewden.lnk");
    const string Scheme = @"Software\Classes\crewden";

    // ProcessStartInfo.ArgumentList is unavailable on the inbox .NET Framework.
    static string Quote(string value) {
        return "\"" + Regex.Replace(value, "(\\\\*)(\"|$)", delegate(Match m) {
            return new string('\\', m.Groups[1].Length * 2) + (m.Groups[2].Length == 0 ? "" : "\\\"");
        }) + "\"";
    }
    internal static string Run(string exe, params string[] args) {
        var info = new ProcessStartInfo(exe, String.Join(" ", args.Select(Quote))) {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
        };
        using (var process = Process.Start(info)) {
            var output = process.StandardOutput.ReadToEndAsync();
            var error = process.StandardError.ReadToEndAsync();
            process.WaitForExit();
            if (process.ExitCode != 0)
                throw new InvalidOperationException((error.Result + "\n" + output.Result).Trim());
            return output.Result.Trim();
        }
    }
    static void Register(string exe, bool firstOnly) {
        using (var current = Registry.CurrentUser.OpenSubKey(Scheme)) {
            if (firstOnly && (current != null || File.Exists(Shortcut))) return;
        }
        dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
        dynamic link = shell.CreateShortcut(Shortcut);
        link.TargetPath = exe;
        link.WorkingDirectory = Path.GetDirectoryName(exe);
        link.Description = "Crewden 电脑端";
        link.Save();
        using (var key = Registry.CurrentUser.CreateSubKey(Scheme)) {
            key.SetValue("", "URL:Crewden");
            key.SetValue("URL Protocol", "");
            using (var command = key.CreateSubKey(@"shell\open\command"))
                command.SetValue("", Quote(exe) + " uri \"%1\"");
        }
    }
    static string Candidate(string hash) { return Path.Combine(Package.Home, "installers", hash); }
    static void Install(string source) {
        Package.PrivateRoot();
        var hash = Package.Hash(source);
        var directory = Candidate(hash);
        Directory.CreateDirectory(Path.GetDirectoryName(directory));
        if (!Directory.Exists(directory)) {
            var stage = Directory.CreateDirectory(directory + "-" + Guid.NewGuid().ToString("N")).FullName;
            try {
                var copy = Path.Combine(stage, Package.Setup);
                File.Copy(source, copy);
                Package.Check(Package.Hash(copy) == hash, "安装器发生变化，请重新下载。");
                File.Copy(Self, Path.Combine(stage, "Crewden.exe"));
                File.Copy(Self + ".config", Path.Combine(stage, "Crewden.exe.config"));
                try { Directory.Move(stage, directory); }
                catch (IOException) { if (!Directory.Exists(directory)) throw; }
            } finally { if (Directory.Exists(stage)) Directory.Delete(stage, true); }
        }
        Register(Path.Combine(directory, "Crewden.exe"), true);
    }
    static string ParseUri(string raw) {
        const string prefix = "crewden://connect?origin=";
        Package.Check(raw.StartsWith(prefix, StringComparison.Ordinal) && raw.Length <= 4096 &&
            raw.IndexOfAny(new char[] {'&', '#', '\\', '"', '\r', '\n'}) < 0, "无法识别此 Crewden 连接。");
        return Package.Origin(Uri.UnescapeDataString(raw.Substring(prefix.Length)));
    }
    static string Cli(string root, params string[] args) {
        return Run(Path.Combine(root, "runtime", "node.exe"),
            new string[] { Path.Combine(root, "apps/node/lib/cli.js") }.Concat(args).ToArray());
    }
    static Form Window(string title, int height) {
        return new Form { Text = title, ClientSize = new Size(530, height), MinimumSize = new Size(470, height + 40),
            StartPosition = FormStartPosition.CenterScreen, AutoScaleMode = AutoScaleMode.Dpi,
            Font = new Font("Microsoft YaHei UI", 10F) };
    }
    static void Connect(string origin, bool confirmed) {
        if (!confirmed && MessageBox.Show("允许这台电脑连接以下 IM 站点？\n\n" + origin,
                "连接 Crewden", MessageBoxButtons.OKCancel, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2)
                != DialogResult.OK) return;
        using (var window = Window("连接 Crewden", 150)) {
            var text = new Label { Dock = DockStyle.Fill, Padding = new Padding(20), Text = "正在获取 " + origin + " 指定的版本…" };
            window.Controls.Add(text);
            bool running = true;
            window.FormClosing += delegate(object sender, FormClosingEventArgs e) { e.Cancel = running; };
            Action<string> report = msg => window.Invoke(new Action(delegate { text.Text = msg; }));
            window.Shown += async delegate {
                try {
                    await Task.Run(delegate {
                        var manifest = Package.Manifest(origin);
                        var candidate = Candidate(manifest.installer.sha256);
                        var exe = Path.Combine(candidate, Package.Setup);
                        var gui = Path.Combine(candidate, "Crewden.exe");
                        Package.Check(File.Exists(exe) && File.Exists(gui) && new FileInfo(exe).Length == manifest.installer.size &&
                            Package.Hash(exe) == manifest.installer.sha256, "这台电脑还没有此 IM 指定的安装器。请返回网页重新下载、安装，再点击连接。");
                        if (!String.Equals(Self, gui, StringComparison.OrdinalIgnoreCase)) {
                            // Dispatch only a candidate whose original installer matches this IM.
                            Run(gui, "connect", origin);
                            return;
                        }
                        var root = Package.Prepare(manifest, report);
                        Register(gui, false);
                        report("请在默认浏览器中确认连接。完成后，回到 IM 查看电脑的上线状态。");
                        Cli(root, "setup", "--im-service-url", origin);
                    });
                    text.Text = "请回到原网页查看连接进度。";
                } catch (Exception error) {
                    text.Text = "连接未完成。请返回原网页重试。\n\n" + error.Message;
                } finally { running = false; }
                if (!confirmed && !String.Equals(text.Text, "请回到原网页查看连接进度。", StringComparison.Ordinal)) return;
                if (text.Text == "请回到原网页查看连接进度。") window.Close();
            };
            Application.Run(window);
        }
    }
    sealed class Connection {
        internal string Config;
        internal string Name;
        internal string Root {
            get {
                var data = Package.Json.Deserialize<Dictionary<string, string>>(File.ReadAllText(
                    Path.Combine(Path.GetDirectoryName(Config), ".windows-active.json")));
                Package.Check(Package.Digest(data["sha256"]), "电脑的当前版本无效。");
                var root = Path.Combine(Package.Home, "versions", data["sha256"]);
                Package.Check(File.Exists(Path.Combine(root, ".ready")), "请从原网页重新打开电脑端安装程序。");
                return root;
            }
        }
        public override string ToString() { return Name; }
    }
    static void Manage() {
        using (var window = Window("Crewden 电脑端", 200)) {
            var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(14), AutoScroll = true };
            var list = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 465 };
            var status = new Label { Width = 465, Height = 60, Text = "返回 IM 网页，点击「连接这台电脑」。" };
            panel.Controls.Add(list);
            panel.Controls.Add(status);
            window.Controls.Add(panel);
            var buttons = new List<Button>();
            var root = Environment.GetEnvironmentVariable("NANO_INSTALL_ROOT") ??
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".nanoassistant");
            var configs = Path.Combine(root, "connections");
            if (Directory.Exists(configs)) foreach (var dir in Directory.GetDirectories(configs)) {
                if (!File.Exists(Path.Combine(dir, ".windows-active.json"))) continue;
                var item = new Connection { Config = Path.Combine(dir, "config.yaml"), Name = Path.GetFileName(dir) };
                try { item.Name = Run(Path.Combine(item.Root, "runtime/node.exe"), Path.Combine(item.Root, "connection-name.cjs"), item.Config); }
                catch (Exception) { /* Keep the repairable connection visible. */ }
                list.Items.Add(item);
            }
            Func<string, Task> action = async verb => {
                var selected = (Connection)list.SelectedItem;
                if (selected == null) return;
                list.Enabled = false;
                buttons.ForEach(button => button.Enabled = false);
                status.Text = "正在读取电脑状态…";
                try {
                    status.Text = await Task.Run(delegate {
                        if (verb != "status") Cli(selected.Root, verb, "--config", selected.Config);
                        var auto = Cli(selected.Root, "autostart-status", "--config", selected.Config);
                        string state;
                        try { state = Cli(selected.Root, "status", "--config", selected.Config); }
                        catch (InvalidOperationException e) { state = e.Message; }
                        return state + "\n登录自启" + (auto == "enabled" ? "已开启" : "已关闭");
                    });
                } catch (Exception error) { status.Text = error.Message; }
                finally { list.Enabled = true; buttons.ForEach(button => button.Enabled = true); }
            };
            var labels = new[] { "启动", "停止", "开启登录自启", "关闭登录自启" };
            var verbs = new[] { "start", "stop", "autostart-on", "autostart-off" };
            for (int i = 0; i < labels.Length; i++) {
                string verb = verbs[i];
                var button = new Button { Text = labels[i], AutoSize = true, Enabled = list.Items.Count > 0 };
                button.Click += async delegate { await action(verb); };
                panel.Controls.Add(button);
                buttons.Add(button);
            }
            list.SelectedIndexChanged += async delegate { await action("status"); };
            window.Shown += delegate { if (list.Items.Count != 0) list.SelectedIndex = 0; };
            Application.Run(window);
        }
    }
    [STAThread]
    static int Main(string[] args) {
        Application.EnableVisualStyles();
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
        bool unattended = args.Length > 0 && args[0] == "prepare";
        try {
            if (args.Length == 0) Manage();
            else if (args.Length == 2 && args[0] == "install") Install(Path.GetFullPath(args[1]));
            else if (args.Length == 2 && args[0] == "uri") Connect(ParseUri(args[1]), false);
            else if (args.Length == 2 && args[0] == "connect") Connect(Package.Origin(args[1]), true);
            else if (args.Length == 3 && unattended) {
                var m = Package.Manifest(Package.Origin(args[1]));
                Package.Check(Package.Digest(args[2]) && m.sha256 == args[2], "IM 已更换目标版本，请重试。");
                Package.Prepare(m, Console.WriteLine);
            } else throw new ArgumentException("无法识别此 Crewden 操作。");
            return 0;
        } catch (Exception error) {
            if (unattended) Console.Error.WriteLine(error.Message);
            else MessageBox.Show(error.Message, "Crewden", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
