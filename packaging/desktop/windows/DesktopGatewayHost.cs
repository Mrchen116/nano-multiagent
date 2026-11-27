// Built against the Windows inbox .NET Framework. Uses CrewdenDesktop-<hash>
// task and crewden-desktop-host-<hash> control pipe so Crewden Desktop coexists
// cleanly with feat-781's lightweight Crewden-Gateway-<hash> installation.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Management;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class DesktopGatewayHost {
    static readonly string Exe = Assembly.GetExecutingAssembly().Location;
    static readonly string Package = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(Exe), @"..\..\.."));
    static readonly SecurityIdentifier User = WindowsIdentity.GetCurrent().User;
    static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();

    static int Main(string[] args) {
        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), Utf8) {AutoFlush = true});
        Console.SetError(new StreamWriter(Console.OpenStandardError(), Utf8) {AutoFlush = true});
        try {
            switch (args[0]) {
                case "prepare-overwrite":
                case "uninstall": StopInstallation(args[1], args[2], args[0] == "uninstall"); return 0;
                case "birth": Console.Write(Birth(Int32.Parse(args[1]))); return 0;
                case "boot":
                case "boot-filetime":
                    using (var os = new ManagementObjectSearcher("SELECT LastBootUpTime FROM Win32_OperatingSystem"))
                    using (var rows = os.Get()) foreach (ManagementObject row in rows) {
                        DateTime boot = ManagementDateTimeConverter.ToDateTime((string)row["LastBootUpTime"]).ToUniversalTime();
                        Console.Write(args[0] == "boot-filetime" ? boot.ToFileTimeUtc() : boot.Ticks); return 0;
                    }
                    throw new Exception("Windows did not report LastBootUpTime");
                case "open-browser":
                    var url = new Uri(args[1], UriKind.Absolute);
                    if ((url.Scheme != "https" && url.Scheme != "http") || url.UserInfo != "") throw new Exception("Invalid account confirmation URL");
                    Process.Start(new ProcessStartInfo(url.AbsoluteUri) {UseShellExecute = true}); return 0;
                case "confirm-transfer":
                    var answer = MessageBox.Show(args[1], "Crewden Desktop", MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
                    Console.Write(answer == DialogResult.Yes ? "yes" : "no"); return 0;
                case "private-directory":
                    var acl = new DirectorySecurity();
                    acl.SetAccessRuleProtection(true, false);
                    acl.AddAccessRule(new FileSystemAccessRule(User, FileSystemRights.FullControl,
                        InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                    var dir = new DirectoryInfo(args[1]);
                    if (!dir.Exists) dir.Create(acl);
                    return 0;
            }
            string config = Path.GetFullPath(args[1]);
            string taskKey = TaskKey(config);
            string pipeKey = PipeKey(config);
            if (args[0] == "serve") return Serve(config, taskKey, pipeKey, Int32.Parse(args[2]), args.Length > 3 ? args[3] : null);
            if (args[0] == "worker") return Worker(config, args[2], args[3]);
            if (args[0] == "launch-worker") {
                Request(pipeKey, "worker " + Int32.Parse(args[3]) + " " + args[4] + " " + Guid.Parse(args[2]).ToString());
                return 0;
            }
            dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
            service.Connect();
            dynamic folder = service.GetFolder("\\");
            if (args[0] == "retire-standalone") {
                RetireStandalone(folder, config);
                Console.Write("retired");
                return 0;
            }
            dynamic task = FindTask(folder, taskKey);
            switch (args[0]) {
                case "stop":
                    if (task == null) {
                        dynamic standalone = FindTask(folder, StandaloneKey(config));
                        if (standalone != null) {
                            if (args[2] != "0" || standalone.GetInstances(0).Count != 0) {
                                try { Request(StandaloneKey(config), "stop " + args[2] + " " + args[3]); }
                                catch (TimeoutException) { }
                                for (int i = 0; i < 100 && standalone.GetInstances(0).Count != 0; i++) Thread.Sleep(100);
                            }
                            standalone.Stop(0);
                            return 0;
                        }
                    }
                    if (args[2] != "0" || (task != null && task.GetInstances(0).Count != 0)) {
                        try {
                            Request(pipeKey, "stop " + args[2] + " " + args[3]);
                        } catch (TimeoutException) {
                            if (task != null) throw;
                            TerminateMatchingProcess(args[2], args.Length > 3 ? args[3] : "");
                        }
                        for (int i = 0; i < 100 && task != null && task.GetInstances(0).Count != 0; i++) Thread.Sleep(100);
                        if (task != null && task.GetInstances(0).Count != 0) throw new Exception("Windows desktop gateway task did not finish");
                    }
                    if (task != null) task.Stop(0);
                    return 0;
                case "autostart-status":
                    Console.Write(Enabled(task) ? "enabled" : "disabled"); return 0;
                case "autostart-on":
                case "autostart-off":
                case "start":
                    bool start = args[0] == "start";
                    bool configured = Boolean.Parse(args[3]);
                    string source = "CrewdenDesktop gateway.autostart=" + configured;
                    bool enable = start ? (task != null && task.Definition.RegistrationInfo.Description == source ? Enabled(task) : configured) : args[0] == "autostart-on";
                    task = Register(service, folder, taskKey, enable, "serve " + Quote(config) + " " + Int32.Parse(args[2]) + " $(Arg0)", source);
                    if (Enabled(task) != enable) throw new Exception("Windows did not apply the requested desktop login setting");
                    if (start) {
                        string origin = args.Length == 6 && args[4] == "--im-service-url" ? Convert.ToBase64String(Utf8.GetBytes(args[5])) : "-";
                        task.Run(origin);
                    }
                    Console.Write(enable ? "enabled" : "disabled"); return 0;
                default: throw new Exception("Unknown DesktopGatewayHost command");
            }
        } catch (Exception ex) {
            Console.Error.WriteLine(ex.Message);
            if (args.Length > 1 && (args[0] == "serve" || args[0] == "worker"))
                File.AppendAllText(Path.Combine(Path.GetDirectoryName(args[1]), "gateway.log"), ex.ToString() + Environment.NewLine);
            return 1;
        }
    }

    static string Hash24(string config) {
        using (var digest = SHA256.Create())
            return BitConverter.ToString(digest.ComputeHash(Utf8.GetBytes(User.Value + "|" + config.ToUpperInvariant()))).Replace("-", "").Substring(0, 24);
    }
    static string TaskKey(string config) { return "CrewdenDesktop-" + Hash24(config); }
    static string PipeKey(string config) { return "crewden-desktop-host-" + Hash24(config); }
    static string StandaloneKey(string config) { return "Crewden-Gateway-" + Hash24(config); }

    // Uninstall cannot depend on an active session or a current version pointer:
    // an old version can still own the registered action after logout or an upgrade.
    static List<string> InstalledTasks(dynamic folder, string versions, bool updates) {
        var names = new List<string>();
        foreach (dynamic task in folder.GetTasks(0)) {
            string name = task.Name;
            if (!Regex.IsMatch(name, updates ? @"^CrewdenDesktop-[0-9A-F]{24}-Update$" : @"^CrewdenDesktop-[0-9A-F]{24}$")) continue;
            dynamic actions = task.Definition.Actions;
            if (actions.Count != 1) continue;
            dynamic action = actions[1];
            if (action.Type != 0) continue;
            string path = action.Path;
            if (!Regex.IsMatch(path, "^" + Regex.Escape(versions) + @"\\[a-f0-9]{64}\\apps\\node\\lib\\DesktopGatewayHost\.exe$", RegexOptions.IgnoreCase)) continue;
            Match args = Regex.Match((string)action.Arguments, updates ? "^worker \"([^\"]+)\" " : "^serve \"([^\"]+)\" ");
            if (args.Success && name == TaskKey(args.Groups[1].Value) + (updates ? "-Update" : "")) names.Add(name);
        }
        return names;
    }

    static void StopInstallation(string shell, string desktopHome, bool uninstall) {
        string versions = Path.Combine(desktopHome, "versions");
        dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
        service.Connect();
        dynamic folder = service.GetFolder("\\");
        foreach (string update in InstalledTasks(folder, versions, true)) {
            dynamic task = FindTask(folder, update);
            if (task != null && task.GetInstances(0).Count != 0) throw new IOException("Desktop update still running");
        }
        // Stop the tray supervisor first so it cannot recreate a gateway task.
        foreach (var process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(shell))) {
            using (process) {
                try {
                    if (!String.Equals(process.MainModule.FileName, shell, StringComparison.OrdinalIgnoreCase)) continue;
                } catch (InvalidOperationException) { if (process.HasExited) continue; throw; }
                catch (Win32Exception ex) { if (ex.NativeErrorCode == 5) continue; throw; } // Inaccessible foreign process.
                process.Kill();
                if (!process.WaitForExit(10000)) throw new IOException("Desktop shell did not stop");
            }
        }
        foreach (string name in InstalledTasks(folder, versions, false)) {
            dynamic task = folder.GetTask(name);
            if (uninstall) task.Enabled = false;
            if (task.GetInstances(0).Count != 0) {
                try { Request("crewden-desktop-host-" + name.Substring("CrewdenDesktop-".Length), "stop 0 "); }
                catch (TimeoutException) { } // A host still starting has no pipe yet.
                task.Stop(0); // Closing the host's job handle also terminates remaining children.
                for (int i = 0; i < 100 && task.GetInstances(0).Count != 0; i++) Thread.Sleep(100);
                if (task.GetInstances(0).Count != 0) throw new IOException("Desktop gateway did not stop");
            }
            if (uninstall) folder.DeleteTask(name, 0);
        }
        if (!uninstall) return;
        foreach (string name in InstalledTasks(folder, versions, true)) {
            dynamic task = FindTask(folder, name);
            if (task == null) continue; // A finishing update removes its own task.
            if (task.GetInstances(0).Count != 0) throw new IOException("Desktop update still running");
            folder.DeleteTask(name, 0);
        }

        string install = Environment.GetEnvironmentVariable("NANO_INSTALL_ROOT") ??
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".nanoassistant");
        string connections = Path.Combine(install, "connections");
        if (!Directory.Exists(connections)) return;
        foreach (string connection in Directory.GetDirectories(connections)) {
            var active = Read(connection, ".desktop-active.json");
            object owner, root;
            if (active != null && active.TryGetValue("managed_by", out owner) && Equals(owner, "crewden-desktop") &&
                active.TryGetValue("version_root", out root) && root is string &&
                String.Equals(Path.GetDirectoryName((string)root), versions, StringComparison.OrdinalIgnoreCase))
                File.Delete(Path.Combine(connection, ".desktop-active.json"));
        }
    }

    static void RetireStandalone(dynamic folder, string config) {
        string legacyKey = StandaloneKey(config);
        dynamic standalone = FindTask(folder, legacyKey);
        if (standalone == null) return;
        if (standalone.GetInstances(0).Count != 0) {
            try { Request(legacyKey, "stop 0 "); }
            catch (Exception) { }
            for (int i = 0; i < 100 && standalone.GetInstances(0).Count != 0; i++) Thread.Sleep(100);
            try { standalone.Stop(0); } catch (Exception) { }
        }
        try { folder.DeleteTask(legacyKey, 0); } catch (Exception) { }
    }

    static void TerminateMatchingProcess(string rawPid, string expectedBirth) {
        int pid;
        if (!Int32.TryParse(rawPid, out pid) || pid <= 0 || String.IsNullOrEmpty(expectedBirth)) return;
        IntPtr handle = OpenProcess(0x101001, false, pid); // SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE
        if (handle == IntPtr.Zero) return;
        try {
            if (WaitForSingleObject(handle, 0) == 258 && Birth(handle) == expectedBirth) {
                TerminateProcess(handle, 0);
                WaitForSingleObject(handle, 5000);
            }
        } finally { CloseHandle(handle); }
    }

    static dynamic FindTask(dynamic folder, string name) {
        try { return folder.GetTask(name); }
        catch (Exception ex) {
            if (ex.HResult == unchecked((int)0x80070002)) return null;
            throw;
        }
    }
    static bool Enabled(dynamic task) {
        return task != null && task.Enabled && task.Definition.Triggers.Count > 0 && task.Definition.Settings.RestartCount > 0;
    }
    static dynamic Register(dynamic service, dynamic folder, string name, bool login, string args, string description) {
        dynamic def = service.NewTask(0);
        def.RegistrationInfo.Description = description;
        def.Principal.UserId = User.Value;
        def.Principal.LogonType = 3; // TASK_LOGON_INTERACTIVE_TOKEN
        def.Principal.RunLevel = 0;
        def.Settings.ExecutionTimeLimit = "PT0S";
        def.Settings.StopIfGoingOnBatteries = false;
        def.Settings.DisallowStartIfOnBatteries = false;
        def.Settings.MultipleInstances = 2; // TASK_INSTANCES_IGNORE_NEW
        if (login) {
            dynamic trigger = def.Triggers.Create(9); // TASK_TRIGGER_LOGON
            trigger.UserId = User.Value;
            def.Settings.RestartInterval = "PT1M";
            def.Settings.RestartCount = 999;
        }
        dynamic action = def.Actions.Create(0);
        action.Path = Exe;
        action.Arguments = args;
        action.WorkingDirectory = Package;
        return folder.RegisterTaskDefinition(name, def, 6, User.Value, null, 3);
    }
    static void ScheduleWorker(string config, string taskKey, string operation, string package) {
        dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
        service.Connect();
        dynamic folder = service.GetFolder("\\");
        string name = taskKey + "-Update";
        dynamic task = FindTask(folder, name);
        if (task != null && task.GetInstances(0).Count > 0) return;
        task = Register(service, folder, name, false, "worker " + Quote(config) + " " + Guid.Parse(operation).ToString() + " " + Quote(package), "Crewden Desktop update coordinator");
        task.Run(null);
    }
    static void ApplyDesktopHostEnv(string package) {
        Environment.SetEnvironmentVariable("CREWDEN_DESKTOP_MANAGED", "1");
        if (String.IsNullOrEmpty(Environment.GetEnvironmentVariable("CREWDEN_DESKTOP_HOME"))) {
            string candidate = Path.GetFullPath(Path.Combine(package, @"..\.."));
            if (Directory.Exists(Path.Combine(candidate, "versions")))
                Environment.SetEnvironmentVariable("CREWDEN_DESKTOP_HOME", candidate);
        }
    }
    static int Worker(string config, string operation, string package) {
        ApplyDesktopHostEnv(package);
        var start = new ProcessStartInfo(Path.Combine(package, @"runtime\node.exe"),
            Quote(Path.Combine(package, @"apps\node\lib\update-worker.js")) + " " + Quote(config) + " " + Guid.Parse(operation).ToString()) {
            UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = package, RedirectStandardOutput = true, RedirectStandardError = true
        };
        using (var log = TextWriter.Synchronized(File.AppendText(Path.Combine(Path.GetDirectoryName(config), "node-update.log"))))
        using (var worker = new Process {StartInfo = start}) {
            worker.OutputDataReceived += (s, e) => { if (e.Data != null) { log.WriteLine(e.Data); log.Flush(); } };
            worker.ErrorDataReceived += (s, e) => { if (e.Data != null) { log.WriteLine(e.Data); log.Flush(); } };
            worker.Start(); worker.BeginOutputReadLine(); worker.BeginErrorReadLine(); worker.WaitForExit();
            int code = worker.ExitCode;
            dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
            service.Connect();
            service.GetFolder("\\").DeleteTask(TaskKey(config) + "-Update", 0);
            return code;
        }
    }
    static Dictionary<string, object> Read(string folder, string file) {
        string path = Path.Combine(folder, file);
        try { return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path)); }
        catch (FileNotFoundException) { return null; }
    }
    static string SelectedPackage(string config) {
        string folder = Path.GetDirectoryName(config);
        var active = Read(folder, ".desktop-active.json");
        var change = Read(folder, ".desktop-switch.json");
        string sha = null;
        if (active != null && active.ContainsKey("sha256") && active["sha256"] is string)
            sha = (string)active["sha256"];
        else if (change != null && change.ContainsKey("previous_sha256") && change["previous_sha256"] is string)
            sha = (string)change["previous_sha256"];
        else
            sha = Path.GetFileName(Package);

        if (change != null) {
            var lease = Read(folder, ".node-update.json");
            if (lease != null && Equals(change["operation_id"], lease["operation_id"]) &&
                Equals(change["worker_birth"], lease["worker_birth"]) && Equals(change["worker_pid"], lease["worker_pid"]) &&
                Birth(Convert.ToInt32(lease["worker_pid"])) == (string)lease["worker_birth"] &&
                DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - Convert.ToInt64(lease["heartbeat"]) < 15000 &&
                (Equals(lease["state"], "switching") || Equals(lease["state"], "verifying")))
                sha = (string)change["target_sha256"];
        }
        if (sha != null && Regex.IsMatch(sha, @"\A[a-f0-9]{64}\z")) {
            string versionsDir = Path.GetDirectoryName(Package);
            if (active != null && active.ContainsKey("version_root") && active["version_root"] is string && ((string)active["version_root"]).Length > 0) {
                string candidateParent = Path.GetDirectoryName((string)active["version_root"]);
                if (Directory.Exists(candidateParent)) versionsDir = candidateParent;
            }
            string selected = Path.Combine(versionsDir, sha);
            if (File.ReadAllText(Path.Combine(selected, ".ready")).Trim() != sha)
                throw new Exception("Desktop Windows release has not finished preparation");
            return selected;
        }
        if (active != null && active.ContainsKey("version_root") && active["version_root"] is string) {
            string root = (string)active["version_root"];
            if (!String.IsNullOrEmpty(root) && File.Exists(Path.Combine(root, @"apps\node\lib\cli.js")))
                return root;
        }
        if (File.Exists(Path.Combine(Package, @"apps\node\lib\cli.js")))
            return Package;
        throw new Exception("Invalid active Crewden Desktop Windows release identity");
    }
    static string Birth(int pid) {
        IntPtr handle = OpenProcess(0x101000, false, pid);
        if (handle == IntPtr.Zero) {
            int error = Marshal.GetLastWin32Error();
            if (error == 87) return "";
            throw new Win32Exception(error);
        }
        try {
            uint state = WaitForSingleObject(handle, 0);
            Check(state == 0 || state == 258);
            return state == 258 ? Birth(handle) : "";
        } finally { CloseHandle(handle); }
    }
    static string Birth(IntPtr handle) {
        long start, exit, kernel, user;
        Check(GetProcessTimes(handle, out start, out exit, out kernel, out user));
        return start.ToString(CultureInfo.InvariantCulture);
    }

    static void Request(string pipeKey, string command) {
        using (var pipe = new NamedPipeClientStream(".", pipeKey, PipeDirection.InOut, PipeOptions.None, TokenImpersonationLevel.Identification)) {
            pipe.Connect(5000);
            using (var writer = new StreamWriter(pipe, Utf8, 1024, true))
            using (var reader = new StreamReader(pipe, Utf8, false, 1024, true)) {
                writer.WriteLine(command); writer.Flush();
                string reply = reader.ReadLine();
                if (reply != "OK") throw new Exception(reply ?? "Desktop gateway control channel closed");
            }
        }
    }
    static NamedPipeServerStream ControlPipe(string pipeKey) {
        var acl = new PipeSecurity();
        acl.SetAccessRuleProtection(true, false);
        acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null), PipeAccessRights.FullControl, AccessControlType.Deny));
        acl.AddAccessRule(new PipeAccessRule(User, PipeAccessRights.FullControl, AccessControlType.Allow));
        return new NamedPipeServerStream(pipeKey, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.None, 4096, 4096, acl);
    }
    static string ResolveNodeBinary(string package) {
        string bundled = Path.Combine(package, @"runtime\node.exe");
        if (File.Exists(bundled)) return bundled;
        string envNode = Environment.GetEnvironmentVariable("CREWDEN_NODE_BIN");
        if (!String.IsNullOrEmpty(envNode) && File.Exists(envNode)) return envNode;
        string cached = Path.Combine(package, @".cache\desktop-archives\node-v24.22.1-win-x64\node.exe");
        if (File.Exists(cached)) return cached;
        return bundled;
    }
    static int Serve(string config, string taskKey, string pipeKey, int grace, string encodedOrigin) {
        string package = SelectedPackage(config);
        ApplyDesktopHostEnv(package);
        string node = ResolveNodeBinary(package);
        string args = Quote(node) + " " + Quote(Path.Combine(package, @"apps\node\lib\cli.js")) + " --foreground --config " + Quote(config);
        if (!String.IsNullOrEmpty(encodedOrigin) && encodedOrigin != "-" && encodedOrigin != "$(Arg0)")
            args += " --im-service-url " + Quote(Utf8.GetString(Convert.FromBase64String(encodedOrigin)));
        using (var pipe = ControlPipe(pipeKey))
        using (var graceful = new ManualResetEvent(false)) {
            var gate = new object();
            GatewayJob child = null;
            var control = new Thread(() => {
                while (true) {
                    try {
                        pipe.WaitForConnection();
                        using (var reader = new StreamReader(pipe, Utf8, false, 1024, true))
                        using (var writer = new StreamWriter(pipe, Utf8, 1024, true)) {
                            try {
                                var fields = (reader.ReadLine() ?? "").Split(' ');
                                bool stop = fields[0] == "stop";
                                if (fields.Length < 3 || (!stop && fields[0] != "worker")) throw new Exception("Unknown host request");
                                lock (gate) {
                                    if (!(stop && fields[1] == "0") && (child == null || Int32.Parse(fields[1]) != child.Pid || fields[2] != child.Birth))
                                        throw new Exception("Gateway process identity changed");
                                    if (stop) {
                                        graceful.Set();
                                        if (child != null) child.Stop(grace);
                                    } else ScheduleWorker(config, taskKey, fields[3], package);
                                }
                                writer.WriteLine("OK");
                            } catch (Exception e) { writer.WriteLine(e.Message); }
                            writer.Flush();
                        }
                        pipe.Disconnect();
                        if (graceful.WaitOne(0)) return;
                    } catch (ObjectDisposedException) { return; }
                    catch (IOException) { if (pipe.IsConnected) pipe.Disconnect(); }
                }
            });
            control.IsBackground = true;
            control.Start();
            int[] crashBackoffMs = new int[] { 1000, 2000, 5000, 15000 };
            int rapidCrashStreak = 0;
            while (true) {
                var runTimer = Stopwatch.StartNew();
                lock (gate) {
                    if (graceful.WaitOne(0)) break;
                    child = new GatewayJob(node, args, package, Path.Combine(Path.GetDirectoryName(config), "gateway.log"));
                }
                try { child.Wait(); }
                finally { lock (gate) { child.Dispose(); child = null; } }
                runTimer.Stop();
                if (graceful.WaitOne(0)) break;
                dynamic scheduler = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
                scheduler.Connect();
                dynamic folder = scheduler.GetFolder("\\");
                dynamic task = FindTask(folder, taskKey);
                if (task == null) return 1;
                if (!Enabled(task)) return 0;
                int waitMs = 2000;
                if (runTimer.ElapsedMilliseconds < 5000) {
                    waitMs = crashBackoffMs[Math.Min(rapidCrashStreak, crashBackoffMs.Length - 1)];
                    rapidCrashStreak++;
                } else {
                    rapidCrashStreak = 0;
                }
                // Back off rapid deterministic startup crashes while preserving recovery after transient exits.
                if (graceful.WaitOne(waitMs)) break;
                if (!Enabled(FindTask(folder, taskKey))) return 0;
            }
            control.Join();
            return 0;
        }
    }

    static string Quote(string arg) {
        return "\"" + Regex.Replace(arg, "(\\\\*)(\"|$)", m =>
            new string('\\', m.Groups[1].Length * 2) + (m.Groups[2].Value == "\"" ? "\\\"" : "")) + "\"";
    }

    sealed class GatewayJob : IDisposable {
        IntPtr job, process;
        AnonymousPipeServerStream input;
        internal int Pid;
        internal string Birth;

        internal GatewayJob(string node, string args, string cwd, string logPath) {
            IntPtr log = IntPtr.Zero;
            var info = new ProcessInfo();
            try {
                job = CreateJobObject(IntPtr.Zero, null);
                Check(job != IntPtr.Zero);
                var limits = new ExtendedLimits();
                limits.Basic.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                Check(SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(limits)));
                input = new AnonymousPipeServerStream(PipeDirection.Out, HandleInheritability.Inheritable);
                var security = new SecurityAttributes {Length = Marshal.SizeOf(typeof(SecurityAttributes)), Inherit = true};
                log = CreateFile(logPath, 4, 3, ref security, 4, 0x80, IntPtr.Zero);
                Check(log != new IntPtr(-1));
                var startup = new Startup {Size = Marshal.SizeOf(typeof(Startup)), Flags = 0x100,
                    Input = input.ClientSafePipeHandle.DangerousGetHandle(), Output = log, Error = log};
                Environment.SetEnvironmentVariable("CREWDEN_SUPERVISED_GATEWAY", "1");
                Check(CreateProcess(node, new StringBuilder(args), IntPtr.Zero, IntPtr.Zero, true, 0x08000004,
                    IntPtr.Zero, cwd, ref startup, out info));
                process = info.Process;
                Check(AssignProcessToJobObject(job, process));
                Pid = info.Pid;
                Birth = DesktopGatewayHost.Birth(process);
                Check(ResumeThread(info.Thread) != UInt32.MaxValue);
                input.DisposeLocalCopyOfClientHandle();
            } catch {
                if (process != IntPtr.Zero) TerminateProcess(process, 1);
                Dispose();
                throw;
            } finally {
                if (log != IntPtr.Zero && log != new IntPtr(-1)) CloseHandle(log);
                if (info.Thread != IntPtr.Zero) CloseHandle(info.Thread);
            }
        }
        internal void Wait() { Check(WaitForSingleObject(process, UInt32.MaxValue) == 0); }
        internal void Stop(int grace) {
            try {
                byte[] message = Utf8.GetBytes("stop\n");
                input.Write(message, 0, message.Length);
                input.Flush();
            } catch (IOException) { }
            uint wait = WaitForSingleObject(process, (uint)grace);
            Check(wait == 0 || wait == 258);
            Check(TerminateJobObject(job, 0));
            for (int i = 0; i < 100; i++) {
                Accounting counts;
                Check(QueryInformationJobObject(job, 1, out counts, Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero));
                if (counts.ActiveProcesses == 0) return;
                Thread.Sleep(50);
            }
            throw new Exception("The Desktop Gateway job still has running processes");
        }
        public void Dispose() {
            if (job != IntPtr.Zero) { CloseHandle(job); job = IntPtr.Zero; }
            if (process != IntPtr.Zero) { CloseHandle(process); process = IntPtr.Zero; }
            if (input != null) input.Dispose();
        }
    }
    static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
        internal long PerProcessUserTime, PerJobUserTime;
        internal uint LimitFlags;
        internal UIntPtr MinWorkingSet, MaxWorkingSet;
        internal uint ActiveProcessLimit;
        internal UIntPtr Affinity;
        internal uint Priority, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
        internal BasicLimits Basic;
        internal ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        internal UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemory, PeakJobMemory;
    }
    [StructLayout(LayoutKind.Sequential)] struct Accounting {
        internal long TotalUserTime, TotalKernelTime, PeriodUserTime, PeriodKernelTime;
        internal uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
    }
    [StructLayout(LayoutKind.Sequential)] struct Startup {
        internal int Size;
        internal IntPtr Reserved, Desktop, Title;
        internal int X, Y, XSize, YSize, XChars, YChars, Fill, Flags;
        internal short Show, ReservedSize;
        internal IntPtr ReservedPtr, Input, Output, Error;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { internal IntPtr Process, Thread; internal int Pid, Tid; }
    [StructLayout(LayoutKind.Sequential)] struct SecurityAttributes {
        internal int Length; internal IntPtr Descriptor; [MarshalAs(UnmanagedType.Bool)] internal bool Inherit;
    }
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr attrs, string name);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job, int kind, ref ExtendedLimits limits, int length);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr job, int kind, out Accounting data, int len, IntPtr returned);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)] static extern IntPtr CreateFile(string path, uint access, uint share, ref SecurityAttributes security, uint creation, uint flags, IntPtr template);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)] static extern bool CreateProcess(string file, StringBuilder args, IntPtr processAttrs, IntPtr threadAttrs, bool inherit, uint flags, IntPtr environment, string cwd, ref Startup startup, out ProcessInfo process);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError=true)] static extern uint WaitForSingleObject(IntPtr handle, uint timeout);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint rights, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetProcessTimes(IntPtr process, out long start, out long exit, out long kernel, out long user);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
}
