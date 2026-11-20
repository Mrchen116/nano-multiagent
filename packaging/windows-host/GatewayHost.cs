// Built against the Windows inbox .NET Framework. The scheduled task and the
// Job Object deliberately have different lifetimes from an authorized update.
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

internal static class GatewayHost {
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
                case "birth": Console.Write(Birth(Int32.Parse(args[1]))); return 0;
                case "boot":
                    using (var os = new ManagementObjectSearcher("SELECT LastBootUpTime FROM Win32_OperatingSystem"))
                    using (var rows = os.Get()) foreach (ManagementObject row in rows) {
                        Console.Write(ManagementDateTimeConverter.ToDateTime((string)row["LastBootUpTime"]).ToUniversalTime().Ticks); return 0;
                    }
                    throw new Exception("Windows did not report LastBootUpTime");
                case "open-browser":
                    var url = new Uri(args[1], UriKind.Absolute);
                    if ((url.Scheme != "https" && url.Scheme != "http") || url.UserInfo != "") throw new Exception("Invalid account confirmation URL");
                    Process.Start(new ProcessStartInfo(url.AbsoluteUri) {UseShellExecute = true}); return 0;
                case "confirm-transfer":
                    var answer = MessageBox.Show(args[1], "Crewden", MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
                    Console.Write(answer == DialogResult.Yes ? "yes" : "no"); return 0;
                case "private-directory":
                    var acl = new DirectorySecurity();
                    acl.SetAccessRuleProtection(true, false);
                    acl.AddAccessRule(new FileSystemAccessRule(User, FileSystemRights.FullControl,
                        InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
                    var dir = new DirectoryInfo(args[1]);
                    // An explicit config path may sit in an existing user directory.
                    // Only the product's own newly created connection directory is re-ACL'd.
                    if (!dir.Exists) dir.Create(acl);
                    return 0;
            }
            string config = Path.GetFullPath(args[1]);
            string key = Key(config);
            if (args[0] == "serve") return Serve(config, key, Int32.Parse(args[2]), args.Length > 3 ? args[3] : null);
            if (args[0] == "worker") return Worker(config, args[2], args[3]);
            if (args[0] == "launch-worker") {
                Request(key, "worker " + Int32.Parse(args[3]) + " " + args[4] + " " + Guid.Parse(args[2]).ToString());
                return 0;
            }
            dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
            service.Connect();
            dynamic folder = service.GetFolder("\\");
            dynamic task = FindTask(folder, key);
            switch (args[0]) {
                case "stop":
                    if (args[2] != "0" || (task != null && task.GetInstances(0).Count != 0)) {
                        Request(key, "stop " + args[2] + " " + args[3]);
                        // Wait for the scheduler to release its instance before an immediate restart.
                        for (int i = 0; i < 100 && task != null && task.GetInstances(0).Count != 0; i++) Thread.Sleep(100);
                        if (task != null && task.GetInstances(0).Count != 0) throw new Exception("Windows task did not finish");
                    }
                    if (task != null) task.Stop(0);
                    return 0;
                case "autostart-status":
                    Console.Write(Enabled(task) ? "enabled" : "disabled"); return 0;
                case "autostart-on":
                case "autostart-off":
                case "start":
                    bool start = args[0] == "start";
                    bool enable = start ? (task == null ? Boolean.Parse(args[3]) : Enabled(task)) : args[0] == "autostart-on";
                    task = Register(service, folder, key, enable, "serve " + Quote(config) + " " + Int32.Parse(args[2]) + " $(Arg0)");
                    if (Enabled(task) != enable) throw new Exception("Windows did not apply the requested login setting");
                    if (start) {
                        string origin = args.Length == 6 && args[4] == "--im-service-url" ? Convert.ToBase64String(Utf8.GetBytes(args[5])) : "-";
                        task.Run(origin);
                    }
                    Console.Write(enable ? "enabled" : "disabled"); return 0;
                default: throw new Exception("Unknown GatewayHost command");
            }
        } catch (Exception ex) {
            Console.Error.WriteLine(ex.Message);
            if (args.Length > 1 && (args[0] == "serve" || args[0] == "worker"))
                File.AppendAllText(Path.Combine(Path.GetDirectoryName(args[1]), "gateway.log"), ex.ToString() + Environment.NewLine);
            return 1;
        }
    }

    static string Key(string config) {
        using (var digest = SHA256.Create())
            return "Crewden-Gateway-" + BitConverter.ToString(digest.ComputeHash(Utf8.GetBytes(User.Value + "|" + config.ToUpperInvariant()))).Replace("-", "").Substring(0, 24);
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
    static dynamic Register(dynamic service, dynamic folder, string name, bool login, string args) {
        dynamic def = service.NewTask(0);
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
        return folder.RegisterTaskDefinition(name, def, 6, User.Value, null, 3); // create or update
    }
    static void ScheduleWorker(string config, string key, string operation, string package) {
        dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
        service.Connect();
        dynamic folder = service.GetFolder("\\");
        // A separate on-demand task survives both the Gateway job and the gateway's scheduler instance.
        string name = key + "-Update";
        dynamic task = FindTask(folder, name);
        if (task != null && task.GetInstances(0).Count > 0) return;
        task = Register(service, folder, name, false, "worker " + Quote(config) + " " + Guid.Parse(operation).ToString() + " " + Quote(package));
        task.Run(null);
    }
    static int Worker(string config, string operation, string package) {
        var start = new ProcessStartInfo(Path.Combine(package, @"runtime\node.exe"),
            Quote(Path.Combine(package, @"apps\node\lib\update-worker.js")) + " " + Quote(config) + " " + Guid.Parse(operation).ToString()) {
            UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = package, RedirectStandardOutput = true, RedirectStandardError = true
        };
        using (var log = TextWriter.Synchronized(File.AppendText(Path.Combine(Path.GetDirectoryName(config), "node-update.log"))))
        using (var worker = new Process {StartInfo = start}) {
            worker.OutputDataReceived += (s, e) => { if (e.Data != null) { log.WriteLine(e.Data); log.Flush(); } };
            worker.ErrorDataReceived += (s, e) => { if (e.Data != null) { log.WriteLine(e.Data); log.Flush(); } };
            worker.Start(); worker.BeginOutputReadLine(); worker.BeginErrorReadLine(); worker.WaitForExit();
            return worker.ExitCode;
        }
    }
    static Dictionary<string, object> Read(string folder, string file) {
        string path = Path.Combine(folder, file);
        try { return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path)); }
        catch (FileNotFoundException) { return null; }
    }
    static string SelectedPackage(string config) {
        string folder = Path.GetDirectoryName(config);
        var active = Read(folder, ".windows-active.json");
        var change = Read(folder, ".windows-switch.json");
        string sha = active != null ? (string)active["sha256"] : change != null ? (string)change["previous_sha256"] : Path.GetFileName(Package);
        if (change != null) {
            var lease = Read(folder, ".node-update.json");
            if (lease != null && Equals(change["operation_id"], lease["operation_id"]) &&
                Equals(change["worker_birth"], lease["worker_birth"]) && Equals(change["worker_pid"], lease["worker_pid"]) &&
                Birth(Convert.ToInt32(lease["worker_pid"])) == (string)lease["worker_birth"] &&
                DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - Convert.ToInt64(lease["heartbeat"]) < 15000 &&
                (Equals(lease["state"], "switching") || Equals(lease["state"], "verifying")))
                sha = (string)change["target_sha256"];
        }
        if (!Regex.IsMatch(sha, @"\A[a-f0-9]{64}\z")) throw new Exception("Invalid active Windows release identity");
        return Path.Combine(Path.GetDirectoryName(Package), sha);
    }
    static string Birth(int pid) {
        IntPtr handle = OpenProcess(0x101000, false, pid); // SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
        if (handle == IntPtr.Zero) {
            int error = Marshal.GetLastWin32Error();
            if (error == 87) return ""; // The process no longer exists.
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

    static void Request(string key, string command) {
        using (var pipe = new NamedPipeClientStream(".", key, PipeDirection.InOut, PipeOptions.None, TokenImpersonationLevel.Identification)) {
            pipe.Connect(5000);
            using (var writer = new StreamWriter(pipe, Utf8, 1024, true))
            using (var reader = new StreamReader(pipe, Utf8)) {
                writer.WriteLine(command); writer.Flush();
                string reply = reader.ReadLine();
                if (reply != "OK") throw new Exception(reply ?? "Gateway control channel closed");
            }
        }
    }
    static NamedPipeServerStream ControlPipe(string key) {
        var acl = new PipeSecurity();
        acl.SetAccessRuleProtection(true, false);
        acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid, null), PipeAccessRights.FullControl, AccessControlType.Deny));
        acl.AddAccessRule(new PipeAccessRule(User, PipeAccessRights.FullControl, AccessControlType.Allow));
        return new NamedPipeServerStream(key, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.None, 4096, 4096, acl);
    }
    static int Serve(string config, string key, int grace, string encodedOrigin) {
        string package = SelectedPackage(config);
        string node = Path.Combine(package, @"runtime\node.exe");
        string args = Quote(node) + " " + Quote(Path.Combine(package, @"apps\node\lib\cli.js")) + " --foreground --config " + Quote(config);
        if (!String.IsNullOrEmpty(encodedOrigin) && encodedOrigin != "-" && encodedOrigin != "$(Arg0)")
            args += " --im-service-url " + Quote(Utf8.GetString(Convert.FromBase64String(encodedOrigin)));
        using (var pipe = ControlPipe(key))
        using (var child = new GatewayJob(node, args, package, Path.Combine(Path.GetDirectoryName(config), "gateway.log"))) {
            var graceful = new ManualResetEvent(false);
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
                                if (!(stop && fields[1] == "0") && (Int32.Parse(fields[1]) != child.Pid || fields[2] != child.Birth))
                                    throw new Exception("Gateway process identity changed");
                                if (stop) { graceful.Set(); child.Stop(grace); }
                                else ScheduleWorker(config, key, fields[3], package);
                                writer.WriteLine("OK");
                            } catch (Exception e) { writer.WriteLine(e.Message); }
                            writer.Flush();
                        }
                        pipe.Disconnect();
                        if (graceful.WaitOne(0)) return;
                    } catch (IOException) { if (pipe.IsConnected) pipe.Disconnect(); }
                }
            });
            control.IsBackground = true;
            control.Start();
            child.Wait();
            if (graceful.WaitOne(0)) { control.Join(); return 0; }
            return 1; // Even an unrequested clean Gateway exit must trigger RestartOnFailure.
        }
    }

    // CommandLineToArgvW escaping for paths, including trailing backslashes.
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
                log = CreateFile(logPath, 4, 3, ref security, 4, 0x80, IntPtr.Zero); // FILE_APPEND_DATA, OPEN_ALWAYS
                Check(log != new IntPtr(-1));
                var startup = new Startup {Size = Marshal.SizeOf(typeof(Startup)), Flags = 0x100,
                    Input = input.ClientSafePipeHandle.DangerousGetHandle(), Output = log, Error = log};
                Environment.SetEnvironmentVariable("CREWDEN_SUPERVISED_GATEWAY", "1");
                // Assignment precedes the child's first instruction, including the first DSH spawn.
                Check(CreateProcess(node, new StringBuilder(args), IntPtr.Zero, IntPtr.Zero, true, 0x08000004,
                    IntPtr.Zero, cwd, ref startup, out info)); // CREATE_NO_WINDOW | CREATE_SUSPENDED
                process = info.Process;
                Check(AssignProcessToJobObject(job, process));
                Pid = info.Pid;
                Birth = GatewayHost.Birth(process);
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
            } catch (IOException) { /* Child already closed stdin. Its job is still ours. */ }
            uint wait = WaitForSingleObject(process, (uint)grace);
            Check(wait == 0 || wait == 258);
            Check(TerminateJobObject(job, 0));
            // A signalled Gateway handle alone does not establish that DSH and its children exited.
            for (int i = 0; i < 100; i++) {
                Accounting counts;
                Check(QueryInformationJobObject(job, 1, out counts, Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero));
                if (counts.ActiveProcesses == 0) return;
                Thread.Sleep(50);
            }
            throw new Exception("The Gateway job still has running processes");
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
