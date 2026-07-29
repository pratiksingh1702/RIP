import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/design/design.dart';
import '../../providers/auth_provider.dart';

class UserProfileButton extends ConsumerWidget {
  const UserProfileButton({super.key});

  void _showProfileSheet(BuildContext context, WidgetRef ref, UserModel user) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            CircleAvatar(
              radius: 36,
              backgroundColor: AppColors.primaryContainer,
              backgroundImage: user.avatarUrl != null ? NetworkImage(user.avatarUrl!) : null,
              child: user.avatarUrl == null
                  ? Text(
                      user.displayName.isNotEmpty ? user.displayName[0].toUpperCase() : 'U',
                      style: AppTextStyles.headlineMd.copyWith(color: AppColors.primary),
                    )
                  : null,
            ),
            const SizedBox(height: 12),
            Text(user.displayName, style: AppTextStyles.headlineSm.copyWith(fontWeight: FontWeight.bold)),
            if (user.email != null) ...[
              const SizedBox(height: 4),
              Text(user.email!, style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary)),
            ],
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.primaryContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.verified_user_rounded, size: 14, color: AppColors.primary),
                  const SizedBox(width: 6),
                  Text(
                    'Authenticated via ${user.authType.toUpperCase()}',
                    style: AppTextStyles.caption.copyWith(color: AppColors.primary, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            ListTile(
              leading: const Icon(Icons.key_rounded, color: AppColors.primary),
              title: Text('API Keys & Credentials', style: AppTextStyles.bodyMdBold),
              subtitle: Text('Manage manual API keys or dev tokens', style: AppTextStyles.bodySm),
              trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.textSecondary),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              tileColor: AppColors.surfaceVariant,
              onTap: () {
                Navigator.pop(ctx);
                context.push('/llm-settings');
              },
            ),
            const SizedBox(height: 16),
            RipButton.outline(
              label: 'Sign Out',
              icon: Icons.logout_rounded,
              onPressed: () async {
                Navigator.pop(ctx);
                await ref.read(authNotifierProvider.notifier).logout();
                if (context.mounted) {
                  context.go('/setup');
                }
              },
              isFullWidth: true,
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userAsync = ref.watch(userProfileFutureProvider);
    final currentUser = ref.watch(currentUserProvider);
    final user = currentUser ?? userAsync.asData?.value;

    if (user == null) {
      return IconButton(
        icon: const Icon(Icons.account_circle_outlined, color: AppColors.textSecondary),
        onPressed: () => context.go('/setup'),
      );
    }

    return GestureDetector(
      onTap: () => _showProfileSheet(context, ref, user),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: CircleAvatar(
          radius: 16,
          backgroundColor: AppColors.primaryContainer,
          backgroundImage: user.avatarUrl != null ? NetworkImage(user.avatarUrl!) : null,
          child: user.avatarUrl == null
              ? Text(
                  user.displayName.isNotEmpty ? user.displayName[0].toUpperCase() : 'U',
                  style: AppTextStyles.bodySmBold.copyWith(color: AppColors.primary),
                )
              : null,
        ),
      ),
    );
  }
}
