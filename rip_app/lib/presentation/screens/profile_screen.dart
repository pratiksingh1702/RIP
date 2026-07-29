import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:rip_app/core/design/design.dart';
import 'package:rip_app/core/api/rip_client.dart';
import 'package:rip_app/presentation/providers/auth_provider.dart';
import 'package:rip_app/presentation/providers/connection_provider.dart';
import 'package:rip_app/presentation/providers/settings_provider.dart';
import 'package:rip_app/presentation/providers/llm_config_provider.dart';
import 'package:rip_app/presentation/widgets/common/rip_button.dart';
import 'package:rip_app/presentation/widgets/sidebar/app_drawer.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _scrollController = ScrollController();
  double _headerT = 0.0;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_handleScroll);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_handleScroll)
      ..dispose();
    super.dispose();
  }

  void _handleScroll() {
    if (!_scrollController.hasClients) return;
    final offset = _scrollController.offset;
    final nextHeaderT = (offset / 80).clamp(0.0, 1.0);
    if ((nextHeaderT - _headerT).abs() > 0.02) {
      setState(() => _headerT = nextHeaderT);
    }
  }

  void _showApiKeyDialog(BuildContext context, WidgetRef ref) {
    final currentKey = ref.read(apiKeyProvider) ?? '';
    final controller = TextEditingController(text: currentKey);

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) {
        final isDark = Theme.of(context).brightness == Brightness.dark;
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF14141A) : Colors.white,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Update Gateway API Key',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isDark ? Colors.white : AppColors.textPrimary),
                ),
                const SizedBox(height: 6),
                Text(
                  'Your API key authorizes requests to LLM context gateway endpoints.',
                  style: TextStyle(fontSize: 12, color: isDark ? Colors.white60 : AppColors.textSecondary),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: controller,
                  obscureText: true,
                  style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                  decoration: InputDecoration(
                    hintText: 'Enter API Key (e.g. rip_sk_...)',
                    hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                    filled: true,
                    fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white60 : AppColors.textSecondary)),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: RipButton.primary(
                        label: 'Save Key',
                        onPressed: () async {
                          HapticFeedback.selectionClick();
                          await ref.read(settingsNotifierProvider.notifier).saveApiKey(controller.text.trim());
                          if (context.mounted) Navigator.pop(context);
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showServerUrlDialog(BuildContext context, WidgetRef ref) {
    final currentUrl = ref.read(serverUrlProvider);
    final controller = TextEditingController(text: currentUrl);

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) {
        final isDark = Theme.of(context).brightness == Brightness.dark;
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF14141A) : Colors.white,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Change RIP Server Endpoint',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isDark ? Colors.white : AppColors.textPrimary),
                ),
                const SizedBox(height: 6),
                Text(
                  'Target URL for Gateway APIs, Neo4j Graph, and Qdrant database.',
                  style: TextStyle(fontSize: 12, color: isDark ? Colors.white60 : AppColors.textSecondary),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: controller,
                  style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                  decoration: InputDecoration(
                    hintText: 'http://192.168.31.113:8000',
                    hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                    filled: true,
                    fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white60 : AppColors.textSecondary)),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: RipButton.primary(
                        label: 'Update URL',
                        onPressed: () async {
                          HapticFeedback.selectionClick();
                          await ref.read(settingsNotifierProvider.notifier).saveServerUrl(controller.text.trim());
                          if (context.mounted) Navigator.pop(context);
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showAddLLMConfigDialog(BuildContext context, WidgetRef ref) {
    final idController = TextEditingController();
    final modelController = TextEditingController();
    final apiKeyController = TextEditingController();
    final baseUrlController = TextEditingController();
    String selectedProvider = 'gemini';

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) {
        final isDark = Theme.of(context).brightness == Brightness.dark;
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF14141A) : Colors.white,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Add Custom LLM Config API',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isDark ? Colors.white : AppColors.textPrimary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Register a new LLM provider model endpoint in the RIP gateway.',
                    style: TextStyle(fontSize: 12, color: isDark ? Colors.white60 : AppColors.textSecondary),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: idController,
                    style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                    decoration: InputDecoration(
                      hintText: 'Config Identifier (e.g. custom-gemini-pro)',
                      hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                      filled: true,
                      fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: selectedProvider,
                    dropdownColor: isDark ? const Color(0xFF1F1F28) : Colors.white,
                    style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                    decoration: InputDecoration(
                      filled: true,
                      fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'gemini', child: Text('Google Gemini')),
                      DropdownMenuItem(value: 'ollama', child: Text('Local Ollama')),
                      DropdownMenuItem(value: 'openai', child: Text('OpenAI')),
                      DropdownMenuItem(value: 'anthropic', child: Text('Anthropic Claude')),
                    ],
                    onChanged: (val) {
                      if (val != null) selectedProvider = val;
                    },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: modelController,
                    style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                    decoration: InputDecoration(
                      hintText: 'Model Name (e.g. gemini-1.5-pro)',
                      hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                      filled: true,
                      fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: apiKeyController,
                    obscureText: true,
                    style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                    decoration: InputDecoration(
                      hintText: 'API Key (Optional)',
                      hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                      filled: true,
                      fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: baseUrlController,
                    style: TextStyle(color: isDark ? Colors.white : Colors.black87),
                    decoration: InputDecoration(
                      hintText: 'Base URL (Optional, e.g. http://localhost:11434)',
                      hintStyle: TextStyle(color: isDark ? Colors.white38 : Colors.black38),
                      filled: true,
                      fillColor: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: Text('Cancel', style: TextStyle(color: isDark ? Colors.white60 : AppColors.textSecondary)),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: RipButton.primary(
                          label: 'Register Config',
                          onPressed: () async {
                            if (idController.text.trim().isEmpty || modelController.text.trim().isEmpty) return;
                            HapticFeedback.selectionClick();
                            try {
                              await ref.read(ripClientProvider).addLLMConfig(
                                    configId: idController.text.trim(),
                                    provider: selectedProvider,
                                    model: modelController.text.trim(),
                                    apiKey: apiKeyController.text.trim(),
                                    baseUrl: baseUrlController.text.trim(),
                                  );
                              ref.invalidate(llmConfigsProvider);
                            } catch (_) {}
                            if (context.mounted) Navigator.pop(context);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF0D0D12) : const Color(0xFFF8F9FA);
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;
    final topPadding = MediaQuery.of(context).padding.top;
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    final userAsync = ref.watch(userProfileFutureProvider);
    final currentUser = ref.watch(currentUserProvider);
    final user = currentUser ?? userAsync.asData?.value;
    final serverUrl = ref.watch(serverUrlProvider);
    final apiKey = ref.watch(apiKeyProvider);
    final currentThemeMode = ref.watch(themeModeProvider);

    final llmConfigsAsync = ref.watch(llmConfigsProvider);
    final preferredConfigId = ref.watch(preferredLLMConfigProvider);

    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const AppDrawer(),
      drawerEdgeDragWidth: MediaQuery.sizeOf(context).width * 0.4,
      backgroundColor: bgColor,
      body: Stack(
        children: [
          // Background Base Color
          ColoredBox(color: bgColor),

          // Infinite Scrollable Content Area (Seamless Single-Screen Layout)
          SingleChildScrollView(
            controller: _scrollController,
            physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
            padding: EdgeInsets.fromLTRB(
              16,
              topPadding + 76,
              16,
              bottomPadding + 40,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // --- 1. HERO IDENTITY HEADER ---
                Row(
                  children: [
                    Stack(
                      children: [
                        CircleAvatar(
                          radius: 34,
                          backgroundColor: isDark ? const Color(0xFF22222E) : const Color(0xFFEFEFF5),
                          backgroundImage: user?.avatarUrl != null ? NetworkImage(user!.avatarUrl!) : null,
                          child: user?.avatarUrl == null
                              ? Text(
                                  user?.displayName.isNotEmpty == true ? user!.displayName[0].toUpperCase() : 'U',
                                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: textColor),
                                )
                              : null,
                        ),
                        Positioned(
                          right: 2,
                          bottom: 2,
                          child: Container(
                            width: 12,
                            height: 12,
                            decoration: BoxDecoration(
                              color: const Color(0xFF22C55E),
                              shape: BoxShape.circle,
                              border: Border.all(color: bgColor, width: 2),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user?.displayName ?? 'pratiksingh1702',
                            style: TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                              color: textColor,
                              letterSpacing: -0.3,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 2),
                          Text(
                            user?.email ?? 'pratiksingh59165@gmail.com',
                            style: TextStyle(fontSize: 13, color: mutedTextColor),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 6),
                          Row(
                            children: [
                              _PillTagWithIcon(
                                icon: const _GithubLogo(size: 12),
                                label: 'GitHub OAuth',
                                isDark: isDark,
                              ),
                              const SizedBox(width: 6),
                              _PillTag(
                                label: 'Full Repo Scope',
                                isDark: isDark,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),


                // --- 3. SYSTEM PREFERENCES & THEME CONTROL ---
                _SectionLabel(title: 'APPEARANCE & SYSTEM PREFERENCES', isDark: isDark),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.palette_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                              const SizedBox(width: 10),
                              Text(
                                'App Theme Mode',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: textColor),
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              children: [
                                _ThemeOptionChip(
                                  label: 'System',
                                  isSelected: currentThemeMode == ThemeMode.system,
                                  isDark: isDark,
                                  onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.system),
                                ),
                                _ThemeOptionChip(
                                  label: 'Light',
                                  isSelected: currentThemeMode == ThemeMode.light,
                                  isDark: isDark,
                                  onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.light),
                                ),
                                _ThemeOptionChip(
                                  label: 'Dark',
                                  isSelected: currentThemeMode == ThemeMode.dark,
                                  isDark: isDark,
                                  onTap: () => ref.read(settingsNotifierProvider.notifier).saveThemeMode(ThemeMode.dark),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      const SizedBox(height: 12),
                      _ActionListTile(
                        iconWidget: Icon(Icons.key_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        title: 'Gateway API Key',
                        subtitle: apiKey != null && apiKey.isNotEmpty ? 'Key: sk-••••••••${apiKey.length > 4 ? apiKey.substring(apiKey.length - 4) : ""}' : 'No API key set (Public Mode)',
                        metaText: 'Configure',
                        isDark: isDark,
                        onTap: () => _showApiKeyDialog(context, ref),
                      ),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      _ActionListTile(
                        iconWidget: Icon(Icons.dns_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        title: 'RIP Server Endpoint',
                        subtitle: serverUrl,
                        metaText: 'Edit URL',
                        isDark: isDark,
                        onTap: () => _showServerUrlDialog(context, ref),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // --- 4. DYNAMIC LLM CONFIGS API SECTION ---
                _SectionLabel(title: 'LLM ROUTER & GATEWAY CONFIG APIS', isDark: isDark),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Active Gateway LLM Config',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: textColor),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Loaded from /gateway/api/workflows/llm-configs',
                                style: TextStyle(fontSize: 11, color: mutedTextColor),
                              ),
                            ],
                          ),
                          IconButton(
                            icon: const Icon(Icons.refresh_rounded, size: 18),
                            tooltip: 'Refresh LLM Configs',
                            onPressed: () {
                              HapticFeedback.selectionClick();
                              ref.invalidate(llmConfigsProvider);
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      llmConfigsAsync.when(
                        data: (configs) {
                          final effectiveConfigs = configs.isNotEmpty
                              ? configs
                              : [
                                  {'config_id': 'gemini-3.1-pro', 'provider': 'gemini', 'model': 'gemini-3.1-pro'},
                                  {'config_id': 'gpt-4o-router', 'provider': 'openai', 'model': 'gpt-4o'},
                                  {'config_id': 'claude-3.5-sonnet', 'provider': 'anthropic', 'model': 'claude-3.5-sonnet'},
                                  {'config_id': 'ollama-local', 'provider': 'ollama', 'model': 'qwen2.5-coder'},
                                ];

                          final activeConfigId = preferredConfigId ?? effectiveConfigs.first['config_id'] ?? 'gemini-3.1-pro';

                          return Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: [
                              ...effectiveConfigs.map((cfg) {
                                final cfgId = cfg['config_id'] ?? cfg['model'] ?? 'Config';
                                final provider = cfg['provider'] ?? 'LLM';
                                final isSelected = activeConfigId == cfgId;

                                return _ModelChip(
                                  label: cfgId,
                                  provider: provider,
                                  isSelected: isSelected,
                                  isDark: isDark,
                                  onTap: () {
                                    ref.read(preferredLLMConfigProvider.notifier).state = cfgId;
                                  },
                                );
                              }),
                              _AddConfigChip(
                                isDark: isDark,
                                onTap: () => _showAddLLMConfigDialog(context, ref),
                              ),
                            ],
                          );
                        },
                        loading: () => const SizedBox(
                          height: 36,
                          child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                        ),
                        error: (err, _) => Row(
                          children: [
                            const Icon(Icons.warning_amber_rounded, size: 16, color: Colors.orangeAccent),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                'Offline Mode: Using cached LLM router configs',
                                style: TextStyle(fontSize: 11.5, color: mutedTextColor),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      const SizedBox(height: 14),
                      _ProgressBarRow(
                        label: 'Gateway Dynamic Context Headroom',
                        value: '10% (1,200 tokens reserve)',
                        percentage: 0.90,
                        isDark: isDark,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // --- 5. USAGE SPARKLINE & PERFORMANCE CHART (from compenets.png) ---
                _SectionLabel(title: 'ANALYTICS & GATEWAY TELEMETRY', isDark: isDark),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Total Gateway Requests',
                                style: TextStyle(fontSize: 12, color: mutedTextColor, fontWeight: FontWeight.w600),
                              ),
                              const SizedBox(height: 2),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.baseline,
                                textBaseline: TextBaseline.alphabetic,
                                children: [
                                  Text(
                                    '24.8K',
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.bold,
                                      color: textColor,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    '+14.2% this week',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              '7 Days',
                              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: mutedTextColor),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      SizedBox(
                        height: 70,
                        width: double.infinity,
                        child: CustomPaint(
                          painter: _SparklinePainter(
                            values: const [12, 18, 15, 24, 30, 22, 38, 32, 45, 52, 48, 62],
                            lineColor: isDark ? Colors.white70 : Colors.black87,
                            fillColor: isDark ? Colors.white : Colors.black,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // --- 6. METRIC CARDS ROW (Compact & Clean) ---
                Row(
                  children: [
                    Expanded(
                      child: _CompactMetricTile(
                        title: 'Tokens Consumed',
                        value: '24,850',
                        subtitle: 'Input: 18.2K | Output: 6.6K',
                        isDark: isDark,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _CompactMetricTile(
                        title: 'Est. API Cost',
                        value: '\$0.024',
                        subtitle: 'Gemini 3.1 Pro tier',
                        isDark: isDark,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: _CompactMetricTile(
                        title: 'Avg Latency',
                        value: '185 ms',
                        subtitle: 'Router response speed',
                        isDark: isDark,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _CompactMetricTile(
                        title: 'Max Context',
                        value: '12,000',
                        subtitle: '10% Reserve Headroom',
                        isDark: isDark,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // --- 7. CONTEXT MEMORY & GRAPH OVERVIEW (Ring & Progress) ---
                _SectionLabel(title: 'WORKSPACE INTELLIGENCE & GRAPH', isDark: isDark),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          SizedBox(
                            width: 54,
                            height: 54,
                            child: CustomPaint(
                              painter: _RingPainter(
                                percentage: 0.68,
                                trackColor: isDark ? Colors.white12 : Colors.black12,
                                progressColor: isDark ? Colors.white70 : Colors.black87,
                              ),
                              child: Center(
                                child: Text(
                                  '68%',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    color: textColor,
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Qdrant Vector Capacity',
                                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: textColor),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  '4,120 active code embeddings stored',
                                  style: TextStyle(fontSize: 12, color: mutedTextColor),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      const SizedBox(height: 16),
                      _ProgressBarRow(
                        label: 'Neo4j Graph Nodes',
                        value: '1,840 nodes',
                        percentage: 0.45,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 12),
                      _ProgressBarRow(
                        label: 'Call Graph Edges',
                        value: '6,310 edges',
                        percentage: 0.82,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 12),
                      _ProgressBarRow(
                        label: 'File Dependency Relations',
                        value: '942 relations',
                        percentage: 0.30,
                        isDark: isDark,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),

                // --- GITHUB DEVELOPER PROFILE & CONTRIBUTION HEATMAP ---
                _SectionLabel(title: 'GITHUB DEVELOPER PROFILE & ACTIVITY', isDark: isDark),
                const SizedBox(height: 10),
                _GithubContributionHeatmap(isDark: isDark),
                const SizedBox(height: 12),
                _GithubStatsRow(isDark: isDark),
                const SizedBox(height: 12),
                _GithubLanguagesCard(isDark: isDark),
                const SizedBox(height: 12),
                _GithubRecentActivityCard(isDark: isDark),
                const SizedBox(height: 24),

                // --- 8. MCP TOOLS & ACTIVE SESSIONS ---
                _SectionLabel(title: 'MCP SOURCES & ACTIVE SESSIONS', isDark: isDark),
                const SizedBox(height: 10),
                Container(
                  decoration: BoxDecoration(
                    color: cardBgColor,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    children: [
                      _ActionListTile(
                        iconWidget: const _GithubLogo(size: 18),
                        title: 'GitHub MCP Integration',
                        subtitle: 'Granted: admin:repo_hook, workflow, user:email',
                        metaText: 'Connected',
                        isDark: isDark,
                        onTap: () {},
                      ),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      _ActionListTile(
                        iconWidget: Icon(Icons.terminal_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        title: 'MCP Export for Agents',
                        subtitle: 'Export RIP tools config for Claude Desktop / Cursor',
                        metaText: 'Export',
                        isDark: isDark,
                        onTap: () {
                          HapticFeedback.selectionClick();
                          context.push('/mcp-export');
                        },
                      ),
                      Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
                      _ActionListTile(
                        iconWidget: Icon(Icons.phonelink_setup_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        title: 'Mobile Session',
                        subtitle: 'Android 14 • IP: 192.168.31.113',
                        metaText: 'Active now',
                        isDark: isDark,
                        onTap: () {},
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),

                // --- 9. SIGN OUT CTA BUTTON ---
                RipButton.destructive(
                  label: 'Sign Out Active Session',
                  icon: const Icon(Icons.logout_rounded, size: 18),
                  isFullWidth: true,
                  onPressed: () async {
                    HapticFeedback.heavyImpact();
                    await ref.read(authNotifierProvider.notifier).logout();
                    if (context.mounted) {
                      context.go('/setup');
                    }
                  },
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),

          // --- TOP FADE GRADIENT OVERLAY (richer header transition) ---
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: topPadding + 110,
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      bgColor,
                      bgColor.withValues(alpha: 0.85),
                      bgColor.withValues(alpha: 0.0),
                    ],
                    stops: const [0.0, 0.55, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // --- BOTTOM FADE GRADIENT OVERLAY (richer footer transition) ---
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: bottomPadding + 70,
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [
                      bgColor,
                      bgColor.withValues(alpha: 0.85),
                      bgColor.withValues(alpha: 0.0),
                    ],
                    stops: const [0.0, 0.55, 1.0],
                  ),
                ),
              ),
            ),
          ),

          // --- SEPARATED FLOATING GLASSMORPHIC TOP BAR COMPONENTS ---
          _ProfileGlassHeader(
            progress: _headerT,
            isDark: isDark,
            userName: user?.displayName ?? 'pratiksingh1702',
            onBackTap: () {
              HapticFeedback.selectionClick();
              if (context.canPop()) {
                context.pop();
              } else {
                context.go('/chat');
              }
            },
            onSettingsTap: () {
              HapticFeedback.selectionClick();
              context.push('/setup');
            },
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// GITHUB CONTRIBUTION MATRIX & DEVELOPER PROFILE COMPONENTS
// =============================================================================

class _GithubContributionHeatmap extends StatelessWidget {
  const _GithubContributionHeatmap({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    // Generate deterministic 52-week contribution sample data (7 days x 52 weeks = 364 boxes)
    final random = math.Random(42);
    final contributions = List.generate(364, (index) {
      final val = random.nextDouble();
      if (val > 0.85) return 4;
      if (val > 0.70) return 3;
      if (val > 0.50) return 2;
      if (val > 0.30) return 1;
      return 0;
    });

    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF14141A) : Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const _GithubLogo(size: 18),
                  const SizedBox(width: 8),
                  Text(
                    '1,284 contributions in 2026',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      color: isDark ? Colors.white : AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
              Text(
                'Streak: 14 days 🔥',
                style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  color: isDark ? const Color(0xFF4ADE80) : const Color(0xFF16A34A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 84,
            width: double.infinity,
            child: CustomPaint(
              painter: _ContributionPainter(
                matrix: contributions,
                isDark: isDark,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Jan 2026 - Present',
                style: TextStyle(fontSize: 10.5, color: mutedTextColor),
              ),
              Row(
                children: [
                  Text('Less ', style: TextStyle(fontSize: 10, color: mutedTextColor)),
                  ...[0, 1, 2, 3, 4].map((level) {
                    return Container(
                      width: 9,
                      height: 9,
                      margin: const EdgeInsets.symmetric(horizontal: 1.5),
                      decoration: BoxDecoration(
                        color: _getHeatmapColor(level, isDark),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    );
                  }),
                  Text(' More', style: TextStyle(fontSize: 10, color: mutedTextColor)),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _getHeatmapColor(int level, bool isDark) {
    if (level == 0) return isDark ? const Color(0xFF161B22) : const Color(0xFFEBEDF0);
    if (level == 1) return const Color(0xFF0E4429);
    if (level == 2) return const Color(0xFF006D32);
    if (level == 3) return const Color(0xFF26A641);
    return const Color(0xFF39D353);
  }
}

class _ContributionPainter extends CustomPainter {
  final List<int> matrix;
  final bool isDark;

  _ContributionPainter({required this.matrix, required this.isDark});

  @override
  void paint(Canvas canvas, Size size) {
    const weeks = 52;
    const days = 7;

    final cellWidth = (size.width - (weeks - 1) * 2.5) / weeks;
    final cellHeight = (size.height - (days - 1) * 2.5) / days;
    final radius = Radius.circular(math.min(cellWidth, cellHeight) * 0.25);

    int idx = 0;
    for (int col = 0; col < weeks; col++) {
      for (int row = 0; row < days; row++) {
        if (idx >= matrix.length) break;
        final level = matrix[idx++];
        final x = col * (cellWidth + 2.5);
        final y = row * (cellHeight + 2.5);

        final paint = Paint()
          ..color = _getColor(level)
          ..style = PaintingStyle.fill;

        canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromLTWH(x, y, cellWidth, cellHeight), radius),
          paint,
        );
      }
    }
  }

  Color _getColor(int level) {
    if (level == 0) return isDark ? const Color(0xFF161B22) : const Color(0xFFEBEDF0);
    if (level == 1) return const Color(0xFF0E4429);
    if (level == 2) return const Color(0xFF006D32);
    if (level == 3) return const Color(0xFF26A641);
    return const Color(0xFF39D353);
  }

  @override
  bool shouldRepaint(covariant _ContributionPainter oldDelegate) => false;
}

class _GithubStatsRow extends StatelessWidget {
  const _GithubStatsRow({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _CompactMetricTile(
            title: 'Public Repos',
            value: '42',
            subtitle: '12 Workspaces',
            isDark: isDark,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _CompactMetricTile(
            title: 'Followers',
            value: '250',
            subtitle: '180 Following',
            isDark: isDark,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _CompactMetricTile(
            title: 'Stars Earned',
            value: '1.2K',
            subtitle: 'across repos',
            isDark: isDark,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _CompactMetricTile(
            title: 'Member Since',
            value: '2021',
            subtitle: 'GitHub Pro',
            isDark: isDark,
          ),
        ),
      ],
    );
  }
}

class _GithubLanguagesCard extends StatelessWidget {
  const _GithubLanguagesCard({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Top Languages Breakdown',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: textColor),
              ),
              Text(
                'Full Repo Index',
                style: TextStyle(fontSize: 11, color: mutedTextColor),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Multi-color stacked progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: SizedBox(
              height: 8,
              child: Row(
                children: [
                  Expanded(flex: 42, child: Container(color: const Color(0xFF00B4D8))), // Dart / Flutter
                  Expanded(flex: 35, child: Container(color: const Color(0xFF3572A5))), // Python
                  Expanded(flex: 15, child: Container(color: const Color(0xFFF1E05A))), // JavaScript / TS
                  Expanded(flex: 8, child: Container(color: const Color(0xFFDEA584))),  // Rust
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: const [
              _LangLegendItem(name: 'Dart / Flutter', percent: '42%', color: Color(0xFF00B4D8)),
              _LangLegendItem(name: 'Python', percent: '35%', color: Color(0xFF3572A5)),
              _LangLegendItem(name: 'TypeScript', percent: '15%', color: Color(0xFFF1E05A)),
              _LangLegendItem(name: 'Rust', percent: '8%', color: Color(0xFFDEA584)),
            ],
          ),
        ],
      ),
    );
  }
}

class _LangLegendItem extends StatelessWidget {
  const _LangLegendItem({required this.name, required this.percent, required this.color});

  final String name;
  final String percent;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 5),
        Text(
          '$name ',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.black87),
        ),
        Text(
          percent,
          style: TextStyle(fontSize: 11, color: isDark ? Colors.white38 : AppColors.textSecondary),
        ),
      ],
    );
  }
}

class _GithubRecentActivityCard extends StatelessWidget {
  const _GithubRecentActivityCard({required this.isDark});

  final bool isDark;

  @override
  Widget build(BuildContext context) {
    final cardBgColor = isDark ? const Color(0xFF14141A) : Colors.white;
    final textColor = isDark ? Colors.white : AppColors.textPrimary;
    final mutedTextColor = isDark ? Colors.white54 : AppColors.textSecondary;

    return Container(
      decoration: BoxDecoration(
        color: cardBgColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 10),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Recent GitHub Activity',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: textColor),
                ),
                Text(
                  'Live Stream',
                  style: TextStyle(fontSize: 11, color: mutedTextColor),
                ),
              ],
            ),
          ),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          _ActivityTile(
            icon: Icons.commit_rounded,
            title: 'Pushed 4 commits to pratiksingh1702/RIP',
            subtitle: 'feat: modernized user profile dashboard with contribution calendar',
            time: '2h ago',
            isDark: isDark,
          ),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          _ActivityTile(
            icon: Icons.call_merge_rounded,
            title: 'Merged PR #24 into main',
            subtitle: 'Upgraded context gateway pipeline & parallel tool router',
            time: '1d ago',
            isDark: isDark,
          ),
          Divider(height: 1, color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06)),
          _ActivityTile(
            icon: Icons.star_border_rounded,
            title: 'Starred google-deepmind/agentic-coding',
            subtitle: 'AI pair programming framework',
            time: '3d ago',
            isDark: isDark,
          ),
        ],
      ),
    );
  }
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.time,
    required this.isDark,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String time;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      child: Row(
        children: [
          Icon(icon, size: 18, color: isDark ? Colors.white70 : Colors.black87),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: isDark ? Colors.white : AppColors.textPrimary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: TextStyle(fontSize: 11, color: isDark ? Colors.white54 : AppColors.textSecondary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            time,
            style: TextStyle(fontSize: 10.5, color: isDark ? Colors.white38 : AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// AUTHENTIC 3RD-PARTY BRAND LOGO VECTOR WIDGETS
// =============================================================================

class _GithubLogo extends StatelessWidget {
  const _GithubLogo({this.size = 18, this.color});

  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final iconColor = color ?? (isDark ? Colors.white : const Color(0xFF24292E));

    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _GithubPainter(color: iconColor),
      ),
    );
  }
}

class _GithubPainter extends CustomPainter {
  final Color color;
  _GithubPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    final scale = size.width / 24.0;
    final path = Path();

    path.moveTo(12 * scale, 1.25 * scale);
    path.cubicTo(6.06 * scale, 1.25 * scale, 1.25 * scale, 5.86 * scale, 1.25 * scale, 11.53 * scale);
    path.cubicTo(1.25 * scale, 16.07 * scale, 4.2 * scale, 19.92 * scale, 8.28 * scale, 21.28 * scale);
    path.cubicTo(8.82 * scale, 21.38 * scale, 9.01 * scale, 21.05 * scale, 9.01 * scale, 20.76 * scale);
    path.cubicTo(9.01 * scale, 20.5 * scale, 9.0 * scale, 19.81 * scale, 9.0 * scale, 18.89 * scale);
    path.cubicTo(6.13 * scale, 19.51 * scale, 5.53 * scale, 17.51 * scale, 5.53 * scale, 17.51 * scale);
    path.cubicTo(5.06 * scale, 16.32 * scale, 4.38 * scale, 16.0 * scale, 4.38 * scale, 16.0 * scale);
    path.cubicTo(3.45 * scale, 15.36 * scale, 4.45 * scale, 15.37 * scale, 4.45 * scale, 15.37 * scale);
    path.cubicTo(5.48 * scale, 15.45 * scale, 6.02 * scale, 16.43 * scale, 6.02 * scale, 16.43 * scale);
    path.cubicTo(6.94 * scale, 18.0 * scale, 8.43 * scale, 17.55 * scale, 9.02 * scale, 17.29 * scale);
    path.cubicTo(9.11 * scale, 16.63 * scale, 9.38 * scale, 16.17 * scale, 9.67 * scale, 15.92 * scale);
    path.cubicTo(7.38 * scale, 15.66 * scale, 4.97 * scale, 14.78 * scale, 4.97 * scale, 10.83 * scale);
    path.cubicTo(4.97 * scale, 9.7 * scale, 5.37 * scale, 8.78 * scale, 6.03 * scale, 8.06 * scale);
    path.cubicTo(5.92 * scale, 7.8 * scale, 5.57 * scale, 6.75 * scale, 6.13 * scale, 5.32 * scale);
    path.cubicTo(6.13 * scale, 5.32 * scale, 7.0 * scale, 5.04 * scale, 9.0 * scale, 6.39 * scale);
    path.cubicTo(9.83 * scale, 6.16 * scale, 10.72 * scale, 6.04 * scale, 11.61 * scale, 6.04 * scale);
    path.cubicTo(12.5 * scale, 6.04 * scale, 13.39 * scale, 6.16 * scale, 14.22 * scale, 6.39 * scale);
    path.cubicTo(16.21 * scale, 5.04 * scale, 17.08 * scale, 5.32 * scale, 17.08 * scale, 5.32 * scale);
    path.cubicTo(17.64 * scale, 6.75 * scale, 17.29 * scale, 7.8 * scale, 17.18 * scale, 8.06 * scale);
    path.cubicTo(17.84 * scale, 8.78 * scale, 18.24 * scale, 9.7 * scale, 18.24 * scale, 10.83 * scale);
    path.cubicTo(18.24 * scale, 14.79 * scale, 15.82 * scale, 15.66 * scale, 13.52 * scale, 15.91 * scale);
    path.cubicTo(13.89 * scale, 16.23 * scale, 14.22 * scale, 16.86 * scale, 14.22 * scale, 17.82 * scale);
    path.cubicTo(14.22 * scale, 19.2 * scale, 14.21 * scale, 20.31 * scale, 14.21 * scale, 20.76 * scale);
    path.cubicTo(14.21 * scale, 21.06 * scale, 14.4 * scale, 21.39 * scale, 14.95 * scale, 21.28 * scale);
    path.cubicTo(19.03 * scale, 19.91 * scale, 21.98 * scale, 16.07 * scale, 21.98 * scale, 11.53 * scale);
    path.cubicTo(21.98 * scale, 5.86 * scale, 17.16 * scale, 1.25 * scale, 12.0 * scale, 1.25 * scale);
    path.close();

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _GithubPainter oldDelegate) => oldDelegate.color != color;
}

class _GeminiLogo extends StatelessWidget {
  const _GeminiLogo({this.size = 14});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _GeminiPainter(),
      ),
    );
  }
}

class _GeminiPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2;

    final path = Path();
    path.moveTo(center.dx, center.dy - r);
    path.quadraticBezierTo(center.dx, center.dy, center.dx + r, center.dy);
    path.quadraticBezierTo(center.dx, center.dy, center.dx, center.dy + r);
    path.quadraticBezierTo(center.dx, center.dy, center.dx - r, center.dy);
    path.quadraticBezierTo(center.dx, center.dy, center.dx, center.dy - r);
    path.close();

    final paint = Paint()
      ..shader = const LinearGradient(
        colors: [Color(0xFF4285F4), Color(0xFF9B51E0), Color(0xFFEA4335)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _OpenAILogo extends StatelessWidget {
  const _OpenAILogo({this.size = 14, this.color});

  final double size;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final iconColor = color ?? (isDark ? Colors.white : const Color(0xFF10A37F));

    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _OpenAIPainter(color: iconColor),
      ),
    );
  }
}

class _OpenAIPainter extends CustomPainter {
  final Color color;
  _OpenAIPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.14
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width * 0.36;

    for (int i = 0; i < 6; i++) {
      final angle = i * (math.pi / 3);
      final p1 = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
      final p2 = Offset(
        center.dx + radius * 0.45 * math.cos(angle + math.pi / 2),
        center.dy + radius * 0.45 * math.sin(angle + math.pi / 2),
      );
      canvas.drawLine(p1, p2, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _OpenAIPainter oldDelegate) => oldDelegate.color != color;
}

class _ClaudeLogo extends StatelessWidget {
  const _ClaudeLogo({this.size = 14});

  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _ClaudePainter(),
      ),
    );
  }
}

class _ClaudePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFD97757)
      ..style = PaintingStyle.fill;

    final center = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2;

    for (int i = 0; i < 6; i++) {
      final angle = i * (math.pi / 3);
      final path = Path();
      path.moveTo(center.dx, center.dy);
      path.lineTo(center.dx + r * 0.85 * math.cos(angle - 0.25), center.dy + r * 0.85 * math.sin(angle - 0.25));
      path.lineTo(center.dx + r * math.cos(angle), center.dy + r * math.sin(angle));
      path.lineTo(center.dx + r * 0.85 * math.cos(angle + 0.25), center.dy + r * 0.85 * math.sin(angle + 0.25));
      path.close();
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _ModelChip extends StatelessWidget {
  const _ModelChip({
    required this.label,
    required this.provider,
    required this.isSelected,
    required this.isDark,
    required this.onTap,
  });

  final String label;
  final String provider;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;

  Widget _getProviderLogo() {
    final p = provider.toLowerCase();
    if (p.contains('gemini')) return const _GeminiLogo(size: 14);
    if (p.contains('openai')) return _OpenAILogo(size: 14, color: isDark ? Colors.white : const Color(0xFF10A37F));
    if (p.contains('anthropic') || p.contains('claude')) return const _ClaudeLogo(size: 14);
    if (p.contains('github')) return _GithubLogo(size: 14, color: isDark ? Colors.white : Colors.black87);
    return Icon(
      Icons.computer_rounded,
      size: 14,
      color: isDark ? Colors.white70 : Colors.black87,
    );
  }

  @override
  Widget build(BuildContext context) {
    final textColor = isSelected
        ? (isDark ? Colors.white : AppColors.primary)
        : (isDark ? Colors.white70 : AppColors.textSecondary);

    final bgColor = isSelected
        ? (isDark ? const Color(0xFF2C2C38) : AppColors.primaryLight)
        : (isDark ? const Color(0xFF1B1B22) : Colors.black.withValues(alpha: 0.04));

    final borderColor = isSelected
        ? (isDark ? Colors.white30 : AppColors.primary.withValues(alpha: 0.3))
        : (isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06));

    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: borderColor),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _getProviderLogo(),
            const SizedBox(width: 6),
            Text(
              '$label ($provider)',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                color: textColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddConfigChip extends StatelessWidget {
  const _AddConfigChip({
    required this.isDark,
    required this.onTap,
  });

  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF1B1B22) : Colors.black.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.06),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.add_rounded,
              size: 14,
              color: isDark ? Colors.white70 : Colors.black87,
            ),
            const SizedBox(width: 4),
            Text(
              'Add API Config',
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: FontWeight.bold,
                color: isDark ? Colors.white70 : Colors.black87,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ThemeOptionChip extends StatelessWidget {
  const _ThemeOptionChip({
    required this.label,
    required this.isSelected,
    required this.isDark,
    required this.onTap,
  });

  final String label;
  final bool isSelected;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        onTap();
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: isSelected
              ? (isDark ? Colors.white24 : Colors.white)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(9),
          boxShadow: isSelected
              ? [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 4)]
              : null,
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11.5,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
            color: isSelected
                ? (isDark ? Colors.white : AppColors.textPrimary)
                : (isDark ? Colors.white54 : AppColors.textSecondary),
          ),
        ),
      ),
    );
  }
}

/// Top Bar with Separated Floating Glassmorphic Components
class _ProfileGlassHeader extends StatelessWidget {
  const _ProfileGlassHeader({
    required this.progress,
    required this.isDark,
    required this.userName,
    required this.onBackTap,
    required this.onSettingsTap,
  });

  final double progress;
  final bool isDark;
  final String userName;
  final VoidCallback onBackTap;
  final VoidCallback onSettingsTap;

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    final glassColor = isDark
        ? const Color(0xFF181820).withValues(alpha: 0.85 + (progress * 0.10))
        : const Color(0xFFF1F3F5).withValues(alpha: 0.85 + (progress * 0.10));

    final border = Border.all(
      color: isDark ? Colors.white12 : Colors.black.withValues(alpha: 0.06),
    );

    return Positioned(
      top: topPadding + 6,
      left: 12,
      right: 12,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // 1. SEPARATE GLASS COMPONENT: Back Arrow Button
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onBackTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Center(
                      child: Icon(
                        Icons.arrow_back_rounded,
                        size: 20,
                        color: isDark ? Colors.white70 : Colors.black87,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 2. SEPARATE GLASS COMPONENT: Profile Name Pill (Compact size, fit content)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 7,
                      height: 7,
                      decoration: const BoxDecoration(
                        color: Color(0xFF22C55E),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.sizeOf(context).width * 0.45,
                      ),
                      child: Text(
                        userName,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                          color: isDark ? Colors.white : Colors.black87,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),

          // 3. SEPARATE GLASS COMPONENT: Settings Icon Button
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
              child: Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: glassColor,
                  borderRadius: BorderRadius.circular(16),
                  border: border,
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onSettingsTap,
                    borderRadius: BorderRadius.circular(16),
                    child: Center(
                      child: Icon(
                        Icons.tune_rounded,
                        size: 20,
                        color: isDark ? Colors.white70 : Colors.black87,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.title, required this.isDark});

  final String title;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w800,
        color: isDark ? Colors.white38 : AppColors.textSecondary,
        letterSpacing: 0.8,
      ),
    );
  }
}

class _PillTag extends StatelessWidget {
  const _PillTag({required this.label, required this.isDark});

  final String label;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w600,
          color: isDark ? Colors.white70 : Colors.black87,
        ),
      ),
    );
  }
}

class _PillTagWithIcon extends StatelessWidget {
  const _PillTagWithIcon({
    required this.icon,
    required this.label,
    required this.isDark,
  });

  final Widget icon;
  final String label;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon,
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white70 : Colors.black87,
            ),
          ),
        ],
      ),
    );
  }
}

class _CompactMetricTile extends StatelessWidget {
  const _CompactMetricTile({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.isDark,
  });

  final String title;
  final String value;
  final String subtitle;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF14141A) : Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.white54 : AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: isDark ? Colors.white : AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 10,
              color: isDark ? Colors.white38 : AppColors.textSecondary,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _ProgressBarRow extends StatelessWidget {
  const _ProgressBarRow({
    required this.label,
    required this.value,
    required this.percentage,
    required this.isDark,
  });

  final String label;
  final String value;
  final double percentage;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: isDark ? Colors.white70 : Colors.black87),
            ),
            Text(
              value,
              style: TextStyle(fontSize: 11.5, color: isDark ? Colors.white54 : AppColors.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: percentage,
            minHeight: 5,
            backgroundColor: isDark ? Colors.white12 : Colors.black12,
            valueColor: AlwaysStoppedAnimation<Color>(
              isDark ? Colors.white70 : Colors.black87,
            ),
          ),
        ),
      ],
    );
  }
}

class _ActionListTile extends StatelessWidget {
  const _ActionListTile({
    required this.iconWidget,
    required this.title,
    required this.subtitle,
    required this.metaText,
    required this.isDark,
    required this.onTap,
  });

  final Widget iconWidget;
  final String title;
  final String subtitle;
  final String metaText;
  final bool isDark;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              iconWidget,
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: isDark ? Colors.white : AppColors.textPrimary),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(fontSize: 11, color: isDark ? Colors.white54 : AppColors.textSecondary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                metaText,
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: isDark ? Colors.white38 : AppColors.textSecondary),
              ),
              const SizedBox(width: 4),
              Icon(Icons.chevron_right_rounded, size: 16, color: isDark ? Colors.white38 : AppColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}

/// Custom Sparkline Chart Painter (Monochromatic in dark mode, matching compenets.png)
class _SparklinePainter extends CustomPainter {
  final List<double> values;
  final Color lineColor;
  final Color fillColor;

  _SparklinePainter({
    required this.values,
    required this.lineColor,
    required this.fillColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;

    final path = Path();
    final fillPath = Path();

    final dx = size.width / (values.length - 1);
    final minY = values.reduce(math.min);
    final maxY = values.reduce(math.max);
    final range = (maxY - minY) == 0 ? 1.0 : (maxY - minY);

    double getY(double val) => size.height - ((val - minY) / range) * (size.height * 0.75) - (size.height * 0.12);

    path.moveTo(0, getY(values[0]));
    fillPath.moveTo(0, size.height);
    fillPath.lineTo(0, getY(values[0]));

    for (int i = 0; i < values.length - 1; i++) {
      final x1 = i * dx;
      final y1 = getY(values[i]);
      final x2 = (i + 1) * dx;
      final y2 = getY(values[i + 1]);
      final cx = (x1 + x2) / 2;

      path.cubicTo(cx, y1, cx, y2, x2, y2);
      fillPath.cubicTo(cx, y1, cx, y2, x2, y2);
    }

    fillPath.lineTo(size.width, size.height);
    fillPath.close();

    final fillPaint = Paint()
      ..style = PaintingStyle.fill
      ..shader = LinearGradient(
        colors: [
          fillColor.withValues(alpha: 0.18),
          fillColor.withValues(alpha: 0.0),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    canvas.drawPath(fillPath, fillPaint);

    final linePaint = Paint()
      ..color = lineColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round;

    canvas.drawPath(path, linePaint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) => false;
}

/// Custom Ring Painter for Radial Charts
class _RingPainter extends CustomPainter {
  final double percentage;
  final Color trackColor;
  final Color progressColor;

  _RingPainter({
    required this.percentage,
    required this.trackColor,
    required this.progressColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - 8) / 2;

    final trackPaint = Paint()
      ..color = trackColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.0;

    canvas.drawCircle(center, radius, trackPaint);

    final progressPaint = Paint()
      ..color = progressColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.0
      ..strokeCap = StrokeCap.round;

    const sweepAngle = 2 * math.pi;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      sweepAngle * percentage,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) => false;
}
