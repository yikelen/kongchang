// The installed executable is a small launcher for the bundled Python app.
// Keeping data and code in the application directory preserves portable mode.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

internal static class KongchangLauncher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string python = Path.Combine(root, "vendor", "python", "pythonw.exe");
            string script = Path.Combine(root, "scripts", "run_app.py");
            if (!File.Exists(python) || !File.Exists(script))
            {
                MessageBox.Show("找不到程序运行文件。请保留完整的安装目录，或重新安装简易控场。",
                    "简易控场", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }

            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = python;
            start.Arguments = "\"" + script + "\"";
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            // Portable launches should not create shortcuts outside the folder.
            start.EnvironmentVariables["KONGCHANG_PORTABLE"] = "1";
            Process.Start(start);
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show("无法启动简易控场：" + error.Message,
                "简易控场", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
