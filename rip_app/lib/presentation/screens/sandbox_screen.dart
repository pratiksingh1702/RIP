import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/sandbox_provider.dart';
import '../widgets/sandbox/terminal_view.dart';
import '../widgets/sandbox/sandbox_status_bar.dart';
import '../widgets/sandbox/environment_picker.dart';

class SandboxScreen extends ConsumerStatefulWidget {
  final String? projectId;
  const SandboxScreen({super.key, this.projectId});

  @override
  ConsumerState<SandboxScreen> createState() => _SandboxScreenState();
}

class _SandboxScreenState extends ConsumerState<SandboxScreen> {
  bool _showEnvPicker = true;

  @override
  void initState() {
    super.initState();
    final state = ref.read(sandboxProvider);
    if (state.sandbox != null) {
      _showEnvPicker = false;
    }
  }

  void _createSandbox(dynamic template) {
    final environment = template is String ? template : (template.id ?? 'python');
    final projectId = widget.projectId ?? 'default';
    ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: environment);
    setState(() => _showEnvPicker = false);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sandboxProvider);

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F23),
      appBar: AppBar(
        backgroundColor: const Color(0xFF16213E),
        title: Text(state.sandbox?.environment ?? 'Project Sandbox'),
        actions: [
          if (state.sandbox != null) ...[
            IconButton(
              icon: const Icon(Icons.camera_alt_outlined),
              tooltip: 'Snapshot',
              onPressed: () {},
            ),
            IconButton(
              icon: const Icon(Icons.folder_open),
              tooltip: 'Files',
              onPressed: () {},
            ),
          ],
        ],
      ),
      body: _showEnvPicker
          ? EnvironmentPicker(onSelect: _createSandbox)
          : state.isLoading
              ? const Center(child: CircularProgressIndicator())
              : state.error != null
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.error_outline, color: Colors.red, size: 48),
                          const SizedBox(height: 16),
                          Text(state.error!, style: const TextStyle(color: Colors.red)),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: () => setState(() => _showEnvPicker = true),
                            child: const Text('Try Again'),
                          ),
                        ],
                      ),
                    )
                  : Column(
                      children: [
                        if (state.sandbox != null) const SandboxStatusBar(),
                        const Expanded(child: TerminalView()),
                      ],
                    ),
    );
  }
}