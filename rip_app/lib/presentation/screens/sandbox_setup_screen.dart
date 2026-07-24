import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/sandbox_provider.dart';
import '../widgets/sandbox/environment_picker.dart';

class SandboxSetupScreen extends ConsumerWidget {
  final String projectId;
  const SandboxSetupScreen({super.key, required this.projectId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0F23),
      appBar: AppBar(backgroundColor: const Color(0xFF16213E), title: const Text('New Sandbox')),
      body: EnvironmentPicker(
        onSelect: (template) {
          ref.read(sandboxProvider.notifier).createSandbox(projectId, environment: template.id);
          Navigator.pushReplacementNamed(context, '/sandbox');
        },
      ),
    );
  }
}
