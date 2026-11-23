// Built only by CI. Serve the exact candidate files on loopback to exercise preparation
// before a tagged public release exists. The production manifest reader has no URL override.
using System;
using System.IO;
internal static class Smoke {
    static int Main(string[] args) {
        var raw = File.ReadAllText(args[0]);
        var m = Package.Json.Deserialize<Package.Release>(raw);
        m.Raw = raw;
        m.Base = args[1];
        m.download_url = m.Base + m.package;
        Console.WriteLine(Package.Prepare(m, Console.WriteLine));
        return 0;
    }
}
