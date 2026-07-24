import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';

/// Progress Bar Component matching base_design.md Section 4
class RipProgressBar extends StatelessWidget {
  final double value; // 0.0 to 1.0
  final Color? color;
  final double height;
  final Color? backgroundColor;

  const RipProgressBar({
    super.key,
    required this.value,
    this.color,
    this.height = 6.0, // Thin track
    this.backgroundColor,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveFillColor = color ?? AppColors.primary;
    final effectiveBgColor = backgroundColor ?? AppColors.border;

    return Container(
      height: height,
      width: double.infinity,
      decoration: BoxDecoration(
        color: effectiveBgColor,
        borderRadius: BorderRadius.circular(9999), // Rounded full track
      ),
      clipBehavior: Clip.antiAlias,
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: value.clamp(0.0, 1.0),
        child: Container(
          decoration: BoxDecoration(
            color: effectiveFillColor,
            borderRadius: BorderRadius.circular(9999),
          ),
        ),
      ),
    );
  }
}

// Backward compatibility alias
class ProgressBar extends StatelessWidget {
  final double progress;
  final Color? color;

  const ProgressBar({
    super.key,
    required this.progress,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return RipProgressBar(value: progress, color: color);
  }
}
