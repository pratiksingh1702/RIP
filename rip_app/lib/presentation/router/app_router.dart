import 'package:go_router/go_router.dart';
import '../screens/splash_screen.dart';
import '../screens/setup_screen.dart';
import '../screens/chat_screen.dart';
import '../screens/gateway_activity_screen.dart';
import '../screens/gateway_audit_screen.dart';
import '../screens/gateway_sources_screen.dart';
import '../screens/mcp_export_screen.dart';

final appRouter = GoRouter(
  initialLocation: '/splash',
  routes: [
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
      path: '/audit',
      builder: (context, state) => const GatewayAuditScreen(),
    ),
    GoRoute(
      path: '/mcp-export',
      builder: (context, state) => const McpExportScreen(),
    ),
  ],
);
