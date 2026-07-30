import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/settings_provider.dart';
import '../providers/auth_provider.dart';
import '../screens/splash_screen.dart';
import '../screens/setup_screen.dart';
import '../screens/chat_screen.dart';
import '../screens/sandbox_screen.dart';
import '../screens/workspace_dashboard.dart';
import '../screens/gateway_activity_screen.dart';
import '../screens/gateway_audit_screen.dart';
import '../screens/gateway_sources_screen.dart';
import '../screens/mcp_export_screen.dart';
import '../screens/agent_runs_screen.dart';
import '../screens/workflows_screen.dart';
import '../screens/llm_settings_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/projects_screen.dart';
import '../widgets/overlays/first_time_github_onboarding_dialog.dart';

class _OAuthCallbackWidget extends ConsumerStatefulWidget {
  final String? apiKey;
  const _OAuthCallbackWidget({this.apiKey});

  @override
  ConsumerState<_OAuthCallbackWidget> createState() => _OAuthCallbackWidgetState();
}

class _OAuthCallbackWidgetState extends ConsumerState<_OAuthCallbackWidget> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final apiKey = widget.apiKey;
      if (apiKey != null && apiKey.isNotEmpty) {
        await ref.read(settingsNotifierProvider.notifier).saveApiKey(apiKey);
        ref.invalidate(userProfileFutureProvider);
        if (mounted) {
          context.go('/chat');
          Future.delayed(const Duration(milliseconds: 300), () {
            final navContext = rootNavigatorKey.currentContext;
            if (navContext != null) {
              showDialog(
                context: navContext,
                builder: (context) => const FirstTimeGithubOnboardingDialog(),
              );
            }
          });
        }
      } else {
        if (mounted) {
          context.go('/setup');
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF0D0D12),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: Color(0xFF38BDF8)),
            SizedBox(height: 16),
            Text(
              'Authenticating user session...',
              style: TextStyle(color: Colors.white70, fontSize: 14),
            ),
          ],
        ),
      ),
    );
  }
}

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: rootNavigatorKey,
  initialLocation: '/splash',
  onException: (context, state, router) {
    final uri = state.uri;
    final apiKey = uri.queryParameters['api_key'];
    if (apiKey != null && apiKey.isNotEmpty) {
      router.go('/oauth-callback?api_key=$apiKey');
    } else {
      router.go('/setup');
    }
  },
  routes: [
    GoRoute(
      path: '/chat',
      builder: (context, state) => const ChatScreen(),
    ),
    GoRoute(
      path: '/sandbox',
      builder: (context, state) => const SandboxScreen(),
    ),
    GoRoute(
      path: '/sandbox/:projectId',
      builder: (context, state) => SandboxScreen(projectId: state.pathParameters['projectId']),
    ),
    GoRoute(path: '/workspace', builder: (context, state) => const WorkspaceDashboard()),
    GoRoute(path: '/splash', builder: (context, state) => const SplashScreen()),
    GoRoute(path: '/setup', builder: (context, state) => const SetupScreen()),
    GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
    GoRoute(path: '/projects', builder: (context, state) => const ProjectsScreen()),
    GoRoute(path: '/activity', builder: (context, state) => const GatewayActivityScreen()),
    GoRoute(path: '/sources', builder: (context, state) => const GatewaySourcesScreen()),
    GoRoute(path: '/workflows', builder: (context, state) {
      final extra = state.extra;
      final payload = extra is Map ? Map<String, dynamic>.from(extra) : const <String, dynamic>{};
      return WorkflowsScreen(initialWorkflowId: payload['workflow_id']?.toString(), initialRunId: payload['run_id']?.toString());
    }),
    GoRoute(path: '/audit', builder: (context, state) => const GatewayAuditScreen()),
    GoRoute(path: '/agent-runs', builder: (context, state) => const AgentRunsScreen()),
    GoRoute(path: '/llm-settings', builder: (context, state) => const LlmSettingsScreen()),
    GoRoute(path: '/mcp-export', builder: (context, state) => const McpExportScreen()),
    GoRoute(
      path: '/oauth/callback',
      builder: (context, state) => _OAuthCallbackWidget(apiKey: state.uri.queryParameters['api_key']),
    ),
    GoRoute(
      path: '/callback',
      builder: (context, state) => _OAuthCallbackWidget(apiKey: state.uri.queryParameters['api_key']),
    ),
    GoRoute(
      path: '/oauth-callback',
      builder: (context, state) => _OAuthCallbackWidget(apiKey: state.uri.queryParameters['api_key']),
    ),
  ],
);
