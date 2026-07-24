import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/design/design.dart';
import '../providers/settings_provider.dart';
import '../providers/project_provider.dart';
import '../providers/connection_provider.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    await ref.read(settingsProvider.future);
    await ref.read(activeProjectNotifierProvider.notifier).loadActiveProject();

    final connectionStatus = await ref.read(connectionStatusProvider.future);

    if (mounted) {
      if (connectionStatus) {
        context.go('/chat');
      } else {
        context.go('/setup');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Mascot Hero Pose
              const RipMascotWidget(
                pose: RipMascotPose.waving,
                width: 150,
                height: 150,
              ),

              const SizedBox(height: 28),
              Text(
                'Welcome to RIP!',
                style: AppTextStyles.headlineLg.copyWith(
                  fontWeight: FontWeight.w700,
                  fontSize: 26,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'AI Developer Assistant',
                style: AppTextStyles.bodyMd.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Chat first. Ship faster. Smile more.',
                style: AppTextStyles.bodySm,
              ),
              const SizedBox(height: 36),
              const SizedBox(
                width: 160,
                child: RipProgressBar(
                  value: 0.7,
                  color: AppColors.primary,
                  height: 4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
