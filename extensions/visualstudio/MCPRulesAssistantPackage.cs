using System;
using System.ComponentModel.Design;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.VisualStudio.Shell;
using Microsoft.VisualStudio.Shell.Interop;
using Task = System.Threading.Tasks.Task;

namespace MCPRulesAssistant
{
    [PackageRegistration(UseManagedResourcesOnly = true, AllowsBackgroundLoading = true)]
    [Guid(MCPRulesAssistantPackage.PackageGuidString)]
    [ProvideMenuResource("Menus.ctmenu", 1)]
    [ProvideToolWindow(typeof(MCPToolWindow))]
    public sealed class MCPRulesAssistantPackage : AsyncPackage
    {
        public const string PackageGuidString = "12345678-1234-1234-1234-123456789012";

        protected override async Task InitializeAsync(CancellationToken cancellationToken, IProgress<ServiceProgressData> progress)
        {
            await this.JoinableTaskFactory.SwitchToMainThreadAsync(cancellationToken);

            var commandService = await GetServiceAsync(typeof(IMenuCommandService)) as OleMenuCommandService;
            if (commandService != null)
            {
                // Status Update Command
                var statusUpdateCommandID = new CommandID(CommandSet, 0x0100);
                var statusUpdateCommand = new MenuCommand(ExecuteStatusUpdate, statusUpdateCommandID);
                commandService.AddCommand(statusUpdateCommand);

                // Coverage Report Command
                var coverageCommandID = new CommandID(CommandSet, 0x0101);
                var coverageCommand = new MenuCommand(ExecuteCoverage, coverageCommandID);
                commandService.AddCommand(coverageCommand);

                // Ingest Rules Command
                var ingestCommandID = new CommandID(CommandSet, 0x0102);
                var ingestCommand = new MenuCommand(ExecuteIngestRules, ingestCommandID);
                commandService.AddCommand(ingestCommand);

                // Generate CI Command
                var generateCICommandID = new CommandID(CommandSet, 0x0103);
                var generateCICommand = new MenuCommand(ExecuteGenerateCI, generateCICommandID);
                commandService.AddCommand(generateCICommand);

                // Show Tool Window Command
                var toolWindowCommandID = new CommandID(CommandSet, 0x0104);
                var toolWindowCommand = new MenuCommand(ShowToolWindow, toolWindowCommandID);
                commandService.AddCommand(toolWindowCommand);
            }
        }

        public static readonly Guid CommandSet = new Guid("87654321-4321-4321-4321-210987654321");

        private void ExecuteStatusUpdate(object sender, EventArgs e)
        {
            ExecuteMCPCommand("status-update");
        }

        private void ExecuteCoverage(object sender, EventArgs e)
        {
            ExecuteMCPCommand("coverage");
        }

        private void ExecuteIngestRules(object sender, EventArgs e)
        {
            ExecuteMCPCommand("ingest-rules README.md docs/");
        }

        private void ExecuteGenerateCI(object sender, EventArgs e)
        {
            ExecuteMCPCommand("generate-ci");
        }

        private void ShowToolWindow(object sender, EventArgs e)
        {
            ThreadHelper.ThrowIfNotOnUIThread();
            var window = this.FindToolWindow(typeof(MCPToolWindow), 0, true);
            if (window?.Frame == null)
            {
                throw new NotSupportedException("Cannot create tool window");
            }

            var windowFrame = (IVsWindowFrame)window.Frame;
            Microsoft.VisualStudio.ErrorHandler.ThrowOnFailure(windowFrame.Show());
        }

        private async void ExecuteMCPCommand(string command)
        {
            await Task.Run(() =>
            {
                try
                {
                    var dte = GetService(typeof(EnvDTE.DTE)) as EnvDTE.DTE;
                    if (dte?.Solution?.FullName == null)
                    {
                        ShowMessage("No solution open", "Error");
                        return;
                    }

                    var solutionDir = Path.GetDirectoryName(dte.Solution.FullName);
                    var mcpDir = Path.Combine(solutionDir, ".mcp");

                    if (!Directory.Exists(mcpDir))
                    {
                        ShowMessage("MCP project not found (.mcp directory missing)", "Error");
                        return;
                    }

                    var pythonBin = Path.Combine(mcpDir, "venv", "Scripts", "python.exe");
                    if (!File.Exists(pythonBin))
                    {
                        ShowMessage("MCP not installed (run install-all-windows.ps1)", "Error");
                        return;
                    }

                    var startInfo = new ProcessStartInfo
                    {
                        FileName = pythonBin,
                        Arguments = $"-m mcp_rules_assistant.cli {command}",
                        WorkingDirectory = solutionDir,
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    };

                    using (var process = Process.Start(startInfo))
                    {
                        var output = process.StandardOutput.ReadToEnd();
                        var error = process.StandardError.ReadToEnd();
                        process.WaitForExit();

                        if (process.ExitCode == 0)
                        {
                            ShowMessage($"Command completed successfully:\n{output}", "MCP Rules Assistant");
                        }
                        else
                        {
                            ShowMessage($"Command failed:\n{error}", "Error");
                        }
                    }
                }
                catch (Exception ex)
                {
                    ShowMessage($"Failed to execute command: {ex.Message}", "Error");
                }
            });
        }

        private void ShowMessage(string message, string title)
        {
            ThreadHelper.JoinableTaskFactory.Run(async delegate
            {
                await ThreadHelper.JoinableTaskFactory.SwitchToMainThreadAsync();
                VsShellUtilities.ShowMessageBox(
                    this,
                    message,
                    title,
                    OLEMSGICON.OLEMSGICON_INFO,
                    OLEMSGBUTTON.OLEMSGBUTTON_OK,
                    OLEMSGDEFBUTTON.OLEMSGDEFBUTTON_FIRST);
            });
        }
    }

    [Guid("87654321-1234-1234-1234-123456789012")]
    public class MCPToolWindow : ToolWindowPane
    {
        public MCPToolWindow() : base(null)
        {
            this.Caption = "MCP Rules Assistant";
            this.Content = new MCPToolWindowControl();
        }
    }
}
