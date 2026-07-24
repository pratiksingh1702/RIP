import 'package:flutter/material.dart';
import '../../../core/design/design.dart';

class TypingIndicator extends StatelessWidget {
  const TypingIndicator({
    super.key,
    this.label = 'Querying repository graph...',
    this.onStop,
  });

  final String label;
  final VoidCallback? onStop;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 10),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(color: AppColors.border, width: 1),
          bottom: BorderSide(color: AppColors.border, width: 1),
        ),
      ),
      child: Row(
        children: [
          const RipMascotWidget(
            pose: RipMascotPose.thinking,
            width: 28,
            height: 28,
          ),
          const SizedBox(width: 12),
          const _AnimatedTypingDots(),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.bodySm.copyWith(
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          if (onStop != null) ...[
            const SizedBox(width: 10),
            RipButton.secondary(
              label: 'Stop',
              icon: const Icon(Icons.stop_rounded, size: 16),
              onPressed: onStop,
            ),

          ],
        ],
      ),
    );
  }
}

class _AnimatedTypingDots extends StatelessWidget {
  const _AnimatedTypingDots();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: const [
        _TypingDot(delay: Duration(milliseconds: 0)),
        SizedBox(width: 4),
        _TypingDot(delay: Duration(milliseconds: 160)),
        SizedBox(width: 4),
        _TypingDot(delay: Duration(milliseconds: 320)),
      ],
    );
  }
}

class _TypingDot extends StatefulWidget {
  final Duration delay;

  const _TypingDot({required this.delay});

  @override
  State<_TypingDot> createState() => _TypingDotState();
}

class _TypingDotState extends State<_TypingDot> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _animation = Tween<double>(begin: 0.3, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    Future.delayed(widget.delay, () {
      if (mounted) {
        _controller.repeat(reverse: true);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _animation,
      child: Container(
        width: 7,
        height: 7,
        decoration: const BoxDecoration(
          color: AppColors.primary,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
