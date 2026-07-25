import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../common/rip_card.dart';
import '../common/status_badge.dart';
import '../common/progress_bar.dart';
import '../../providers/sandbox_provider.dart';

class SandboxStatusBar extends ConsumerWidget {
  final VoidCallback? onChangeEnvTap;
  final VoidCallback? onFilesTap;

  const SandboxStatusBar({
    super.key,
    this.onChangeEnvTap,
    this.onFilesTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(sandboxProvider);
    final status = state.status;
    final env = state.sandbox?.environment.toUpperCase() ?? 'PYTHON 3.11';
    final isRunning = status?.status == 'running' || state.sandbox != null;

    final memoryMb = ((status?.memoryUsedBytes ?? 256 * 1024 * 1024) / 1024 / 1024).toDouble();
    final memoryLimitMb = ((status?.memoryLimitBytes ?? 2048 * 1024 * 1024) / 1024 / 1024).toDouble();
    final memoryPercent = status?.memoryPercent != null && status!.memoryPercent > 0
        ? status.memoryPercent / 100
        : (memoryMb / memoryLimitMb).clamp(0.0, 1.0);
    final cpuPercent = (status?.cpuPercent ?? 12.0) / 100.0;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: RipCard(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              children: [
                // Environment & Status Dot
                InkWell(
                  onTap: onChangeEnvTap,
                  borderRadius: BorderRadius.circular(9999),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      borderRadius: BorderRadius.circular(9999),
                      border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        RipStatusDot(
                          type: isRunning ? RipStatusType.success : RipStatusType.danger,
                          size: 8,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          env,
                          style: AppTextStyles.bodyMdBold.copyWith(color: AppColors.primary, fontSize: 12),
                        ),
                        const SizedBox(width: 4),
                        const Icon(
                          Icons.keyboard_arrow_down_rounded,
                          color: AppColors.primary,
                          size: 16,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                RipStatusBadge(
                  label: isRunning ? 'Running / Healthy' : 'Offline',
                  type: isRunning ? RipStatusType.success : RipStatusType.danger,
                ),
                const Spacer(),
                if (onFilesTap != null)
                  IconButton(
                    icon: const Icon(Icons.folder_open_rounded, color: AppColors.primary, size: 20),
                    tooltip: 'Workspace Files Inspector',
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    onPressed: onFilesTap,
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                // CPU Metric
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('CPU Usage', style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary)),
                          Text(
                            '${(cpuPercent * 100).toStringAsFixed(1)}%',
                            style: AppTextStyles.codeSm.copyWith(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      RipProgressBar(value: cpuPercent.clamp(0.0, 1.0)),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                // Memory Metric
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('RAM Usage', style: AppTextStyles.bodySm.copyWith(color: AppColors.textSecondary)),
                          Text(
                            '${memoryMb.toStringAsFixed(0)} / ${memoryLimitMb.toStringAsFixed(0)} MB',
                            style: AppTextStyles.codeSm.copyWith(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      RipProgressBar(value: memoryPercent.clamp(0.0, 1.0)),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
