import 'package:flutter/material.dart';

class ProgressBar extends StatelessWidget {
  final double progress;
  final Color? color;

  const ProgressBar({super.key, required this.progress, this.color});

  @override
  Widget build(BuildContext context) {
    final effectiveColor = color ?? Theme.of(context).colorScheme.primary;

    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: LinearProgressIndicator(
        value: progress.clamp(0, 1),
        backgroundColor: effectiveColor.withOpacity(0.2),
        valueColor: AlwaysStoppedAnimation<Color>(effectiveColor),
        minHeight: 8,
      ),
    );
  }
}
