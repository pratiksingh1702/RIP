import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/design/design.dart';
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
  bool _isConnected = false;
  String? _connectionError;
  bool _showAdvancedSettings = false;

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
      // Defaults are optional during first setup
    }
  }

  Future<void> _testConnection() async {
    setState(() {
      _isTestingConnection = true;
      _connectionError = null;
      _isConnected = false;
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
          setState(() {
            _isConnected = true;
          });
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

  void _onContinue() {
    context.go('/chat');
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
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const SizedBox(height: 12),
                    // Header Title (Match image)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Text(
                          '👋 ',
                          style: TextStyle(fontSize: 24),
                        ),
                        Text(
                          'Welcome to RIP!',
                          style: AppTextStyles.headlineLg.copyWith(
                            fontWeight: FontWeight.w700,
                            fontSize: 24,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      "Let's connect to your server\nand unlock the magic.",
                      textAlign: TextAlign.center,
                      style: AppTextStyles.bodySm.copyWith(
                        color: AppColors.textSecondary,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 28),

                    // Standard Form Controls (Match image)
                    RipTextField(
                      label: 'Server URL',
                      controller: _serverUrlController,
                      hintText: 'https://rip.yourserver.com',
                      keyboardType: TextInputType.url,
                    ),
                    const SizedBox(height: 16),
                    RipTextField(
                      label: 'API Key',
                      controller: _apiKeyController,
                      hintText: '••••••••••••',
                      isPassword: true,
                    ),
                    const SizedBox(height: 24),

                    // Primary Test Connection Button (Match image)
                    RipButton.primary(
                      label: _isTestingConnection ? 'Testing Connection...' : 'Test Connection',
                      onPressed: _isTestingConnection ? null : _testConnection,
                      isLoading: _isTestingConnection,
                      isFullWidth: true,
                    ),

                    // Connection Error Feedback
                    if (_connectionError != null) ...[
                      const SizedBox(height: 16),
                      RipImpactCard(
                        title: 'Connection Error',
                        description: _connectionError!,
                        severity: RipImpactSeverity.high,
                      ),
                    ],

                    // Inline Success Confirmation (Match image)
                    if (_isConnected) ...[
                      const SizedBox(height: 16),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        decoration: BoxDecoration(
                          color: const Color(0xFFDCFCE7),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFF86EFAC), width: 1),
                        ),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(4),
                              decoration: const BoxDecoration(
                                color: Color(0xFF22C55E),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.check_rounded,
                                color: Colors.white,
                                size: 14,
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'Connected successfully! 🎉',
                                style: AppTextStyles.bodyMdBold.copyWith(
                                  color: const Color(0xFF15803D),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      // Primary Continue Button (Match image)
                      RipButton.primary(
                        label: 'Continue',
                        onPressed: _onContinue,
                        isFullWidth: true,
                      ),
                    ],

                    const SizedBox(height: 20),

                    // Advanced Gateway Options Toggle
                    InkWell(
                      onTap: () {
                        setState(() {
                          _showAdvancedSettings = !_showAdvancedSettings;
                        });
                      },
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              'Advanced Gateway Settings',
                              style: AppTextStyles.bodySm.copyWith(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Icon(
                              _showAdvancedSettings
                                  ? Icons.keyboard_arrow_up_rounded
                                  : Icons.keyboard_arrow_down_rounded,
                              size: 18,
                              color: AppColors.primary,
                            ),
                          ],
                        ),
                      ),
                    ),

                    if (_showAdvancedSettings) ...[
                      const SizedBox(height: 12),
                      RipCard(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            DropdownButtonFormField<String>(
                              initialValue: _role,
                              style: AppTextStyles.bodyMd,
                              decoration: const InputDecoration(
                                labelText: 'Default Role',
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
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                Expanded(
                                  child: RipTextField(
                                    label: 'Token Budget',
                                    controller: _maxTokensController,
                                    keyboardType: TextInputType.number,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: RipTextField(
                                    label: 'Reserve %',
                                    controller: _reserveController,
                                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            RipTextField(
                              label: 'Minimum Per Source',
                              controller: _minPerSourceController,
                              keyboardType: TextInputType.number,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),

            // Seated Bottom Mascot Hero (Match image)
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 16),
              child: RipMascotWidget(
                pose: _isConnected
                    ? RipMascotPose.success
                    : (_connectionError != null
                        ? RipMascotPose.error
                        : RipMascotPose.waving),
                width: 130,
                height: 130,
              ),
            ),

          ],
        ),
      ),
    );
  }
}
