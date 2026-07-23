import 'package:go_router/go_router.dart';
import '../screens/splash_screen.dart';
import '../screens/setup_screen.dart';
import '../screens/chat_screen.dart';
import '../screens/workspace_dashboard.dart';
import '../screens/gateway_activity_screen.dart';
import '../screens/gateway_audit_screen.dart';
import '../screens/gateway_sources_screen.dart';
import '../screens/mcp_export_screen.dart';
import '../screens/agent_runs_screen.dart';
import '../screens/workflows_screen.dart';
import '../screens/llm_settings_screen.dart';

final appRouter = GoRouter(
  initialLocation: '/workspace',
  routes: [
    GoRoute(path: '/workspace', builder: (context, state) => const WorkspaceDashboard()),
    GoRoute(
      path: '/splash',
      builder: (context, state) => const SplashScreen(),
    ),
    GoRoute(
      path: '/setup',
      builder: (context, state) => const SetupScreen(),
    ),
    GoRoute(
      path: '/chat',
      builder: (context, state) => const ChatScreen(),
    ),
    GoRoute(
      path: '/activity',
      builder: (context, state) => const GatewayActivityScreen(),
    ),
    GoRoute(
      path: '/sources',
      builder: (context, state) => const GatewaySourcesScreen(),
    ),
    GoRoute(
      path: '/workflows',
      builder: (context, state) {
        final extra = state.extra;
        final payload = extra is Map ? Map<String, dynamic>.from(extra) : const <String, dynamic>{};
        return WorkflowsScreen(
          initialWorkflowId: payload['workflow_id']?.toString(),
          initialRunId: payload['run_id']?.toString(),
        );
      },
    ),
    GoRoute(
      path: '/audit',
      builder: (context, state) => const GatewayAuditScreen(),
    ),
        GoRoute(
      path: '/agent-runs',
      builder: (context, state) => const AgentRunsScreen(),
    ),

    GoRoute(path: '/llm-settings', builder: (context, state) => const LlmSettingsScreen()),
    GoRoute(path: '/agent-runs', builder: (context, state) => const AgentRunsScreen()),
    GoRoute(
      path: '/mcp-export',
      builder: (context, state) => const McpExportScreen(),
    ),
  ],
);



