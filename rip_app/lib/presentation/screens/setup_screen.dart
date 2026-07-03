import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/settings_provider.dart';
import '../providers/gateway_provider.dart';
import '../../core/api/rip_client.dart';

class SetupScreen extends ConsumerStatefulWidget {
  const SetupScreen({super.key});

  @override
  ConsumerState<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends ConsumerState<SetupScreen> {
  final _serverUrlController = TextEditingController();
  final _apiKeyController = TextEditingController();
  final _maxTokensController = TextEditingController(text: '12000');
  final _reserveController = TextEditingController(text: '0.10');
  final _minPerSourceController = TextEditingController(text: '500');
  String _role = 'developer';
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
    final role = ref.read(gatewayRoleProvider);
    setState(() {
      _serverUrlController.text = serverUrl;
      _apiKeyController.text = apiKey ?? '';
      _role = role;
    });
    try {
      final defaults = await RipClient(
        serverUrl: serverUrl,
        apiKey: apiKey?.isEmpty == true ? null : apiKey,
      ).gatewaySettings();
      if (!mounted) return;
      setState(() {
        _maxTokensController.text = '${defaults['default_max_tokens'] ?? 12000}';
        _reserveController.text = '${defaults['overhead_reserve_ratio'] ?? 0.10}';
        _minPerSourceController.text = '${defaults['min_tokens_per_source'] ?? 500}';
        _role = '${defaults['default_role'] ?? role}';
      });
    } catch (_) {
      // Defaults are optional during first setup, before the server is reachable.
    }
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
          ref.read(gatewayRoleProvider.notifier).state = _role;
          await _saveGatewayDefaults(client);
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
    _maxTokensController.dispose();
    _reserveController.dispose();
    _minPerSourceController.dispose();
    super.dispose();
  }

  Future<void> _saveGatewayDefaults(RipClient client) async {
    await client.updateGatewaySettings({
      'default_role': _role,
      'default_max_tokens': int.tryParse(_maxTokensController.text.trim()) ?? 12000,
      'overhead_reserve_ratio': double.tryParse(_reserveController.text.trim()) ?? 0.10,
      'min_tokens_per_source': int.tryParse(_minPerSourceController.text.trim()) ?? 500,
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Setup RIP'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.asset(
                  'assets/images/app_icon.png',
                  width: 120,
                  height: 120,
                  fit: BoxFit.cover,
                ),
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
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _role,
                decoration: const InputDecoration(
                  labelText: 'Default role',
                  prefixIcon: Icon(Icons.admin_panel_settings_outlined),
                ),
                items: const [
                  DropdownMenuItem(value: 'junior_dev', child: Text('Junior developer')),
                  DropdownMenuItem(value: 'developer', child: Text('Developer')),
                  DropdownMenuItem(value: 'senior_dev', child: Text('Senior developer')),
                  DropdownMenuItem(value: 'ci_agent', child: Text('CI agent')),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _role = value);
                },
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _maxTokensController,
                      decoration: const InputDecoration(
                        labelText: 'Token budget',
                        prefixIcon: Icon(Icons.speed_rounded),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _reserveController,
                      decoration: const InputDecoration(
                        labelText: 'Reserve %',
                        prefixIcon: Icon(Icons.pie_chart_outline_rounded),
                      ),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _minPerSourceController,
                decoration: const InputDecoration(
                  labelText: 'Minimum per source',
                  prefixIcon: Icon(Icons.account_tree_outlined),
                ),
                keyboardType: TextInputType.number,
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
