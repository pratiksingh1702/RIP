import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/settings_provider.dart';
import '../../core/api/rip_client.dart';

class SetupScreen extends ConsumerStatefulWidget {
  const SetupScreen({super.key});

  @override
  ConsumerState<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends ConsumerState<SetupScreen> {
  final _serverUrlController = TextEditingController();
  final _apiKeyController = TextEditingController();
  bool _isTestingConnection = false;
  String? _connectionError;

  @override
  void initState() {
    super.initState();
    _loadSavedSettings();
  }

  Future<void> _loadSavedSettings() async {
    await ref.read(settingsProvider.future);
    final serverUrl = ref.read(serverUrlProvider);
    final apiKey = ref.read(apiKeyProvider);
    setState(() {
      _serverUrlController.text = serverUrl;
      _apiKeyController.text = apiKey ?? '';
    });
  }

  Future<void> _testConnection() async {
    setState(() {
      _isTestingConnection = true;
      _connectionError = null;
    });

    try {
      final client = RipClient(
        serverUrl: _serverUrlController.text,
        apiKey: _apiKeyController.text.isEmpty ? null : _apiKeyController.text,
      );
      final isConnected = await client.healthCheck();

      if (isConnected) {
        await ref
            .read(settingsNotifierProvider.notifier)
            .saveServerUrl(_serverUrlController.text);
        if (_apiKeyController.text.isNotEmpty) {
          await ref
              .read(settingsNotifierProvider.notifier)
              .saveApiKey(_apiKeyController.text);
        }
        if (mounted) {
          context.go('/chat');
        }
      } else {
        setState(() {
          _connectionError = 'Server responded but not healthy';
        });
      }
    } catch (e) {
      setState(() {
        _connectionError = e.toString();
      });
    } finally {
      setState(() {
        _isTestingConnection = false;
      });
    }
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Setup RIP'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(
                Icons.settings,
                size: 80,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(
                'Connect to RIP Server',
                style: Theme.of(context).textTheme.headlineMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Enter your server details to get started',
                style: Theme.of(context).textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              TextField(
                controller: _serverUrlController,
                decoration: const InputDecoration(
                  labelText: 'Server URL',
                  hintText: 'http://localhost:8000',
                  prefixIcon: Icon(Icons.link),
                ),
                keyboardType: TextInputType.url,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _apiKeyController,
                decoration: const InputDecoration(
                  labelText: 'API Key (optional)',
                  hintText: 'Enter your API key if required',
                  prefixIcon: Icon(Icons.key),
                ),
                obscureText: true,
              ),
              if (_connectionError != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _connectionError!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onErrorContainer,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: _isTestingConnection ? null : _testConnection,
                child: _isTestingConnection
                    ? const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                          SizedBox(width: 12),
                          Text('Connecting...'),
                        ],
                      )
                    : const Text('Connect'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
