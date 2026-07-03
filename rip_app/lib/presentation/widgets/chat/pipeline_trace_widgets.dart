import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/app_colors.dart';
import '../../../data/models/pipeline_trace.dart';
import '../../providers/connection_provider.dart';

class PipelineStepList extends StatelessWidget {
  final PipelineTrace trace;

  const PipelineStepList({super.key, required this.trace});

  @override
  Widget build(BuildContext context) {
    final events = trace.events;
    if (events.isEmpty) {
      return const _PlainWorkingIndicator();
    }

    final conflict = events.where((event) => event.stage == 'conflict_found').toList();
    final rows = events
        .where((event) => event.stage != 'conflict_found' && event.stage != 'done')
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ...conflict.map((event) => _ConflictBanner(event: event)),
        ...rows.map((event) => _PipelineRow(event: event)),
      ],
    );
  }
}

class PipelineSummaryChip extends ConsumerStatefulWidget {
  final PipelineTrace trace;

  const PipelineSummaryChip({super.key, required this.trace});

  @override
  ConsumerState<PipelineSummaryChip> createState() => _PipelineSummaryChipState();
}

class _PipelineSummaryChipState extends ConsumerState<PipelineSummaryChip> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final conflict = widget.trace.events
        .where((event) => event.stage == 'conflict_found')
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ...conflict.map((event) => _ConflictBanner(event: event)),
        InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () => setState(() => _expanded = !_expanded),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppColors.primary.withValues(alpha: 0.22)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.route_rounded, size: 15, color: AppColors.primary),
                const SizedBox(width: 7),
                Flexible(
                  child: Text(
                    widget.trace.summaryLabel(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Icon(
                  _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                  size: 16,
                  color: AppColors.textSecondary,
                ),
              ],
            ),
          ),
        ),
        AnimatedCrossFade(
          duration: const Duration(milliseconds: 180),
          firstChild: const SizedBox.shrink(),
          secondChild: Padding(
            padding: const EdgeInsets.only(top: 8),
            child: PipelineStepList(trace: widget.trace),
          ),
          crossFadeState:
              _expanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: _FeedbackRow(
            sessionId: widget.trace.sessionId,
          ),
        ),
      ],
    );
  }
}

class _PipelineRow extends StatelessWidget {
  final PipelineEvent event;

  const _PipelineRow({required this.event});

  @override
  Widget build(BuildContext context) {
    final warning = event.status == 'failed' || event.status == 'skipped';
    final done = event.status == 'done';
    final color = warning
        ? const Color(0xFFFBBF24)
        : done
            ? const Color(0xFF34D399)
            : AppColors.primary;
    final icon = warning
        ? Icons.warning_amber_rounded
        : done
            ? Icons.check_circle_rounded
            : Icons.sync_rounded;
    final meta = _metaLabel(event);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              event.detail,
              style: TextStyle(
                color: warning
                    ? const Color(0xFFFDE68A)
                    : AppColors.textPrimary.withValues(alpha: 0.92),
                fontSize: 12,
                height: 1.35,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          if (meta.isNotEmpty) ...[
            const SizedBox(width: 8),
            Text(
              meta,
              style: TextStyle(
                color: AppColors.textSecondary.withValues(alpha: 0.72),
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _metaLabel(PipelineEvent event) {
    final count = event.meta['count'];
    final ms = event.meta['ms'];
    final tokens = event.meta['tokens'] ?? event.meta['after_tokens'];
    final parts = <String>[
      if (count != null) '$count',
      if (tokens != null) '$tokens tok',
      if (ms != null) '${ms}ms',
    ];
    return parts.join(' - ');
  }
}

class _ConflictBanner extends StatelessWidget {
  final PipelineEvent event;

  const _ConflictBanner({required this.event});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF7F1D1D).withValues(alpha: 0.22),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFF87171).withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          const Icon(Icons.report_rounded, size: 17, color: Color(0xFFFCA5A5)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              event.detail,
              style: const TextStyle(
                color: Color(0xFFFECACA),
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PlainWorkingIndicator extends StatelessWidget {
  const _PlainWorkingIndicator();

  @override
  Widget build(BuildContext context) {
    return Text(
      'Working...',
      style: TextStyle(
        color: AppColors.textSecondary.withValues(alpha: 0.78),
        fontSize: 12,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _FeedbackRow extends ConsumerWidget {
  final String sessionId;

  const _FeedbackRow({
    required this.sessionId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        _FeedbackButton(
          label: 'Good',
          icon: Icons.thumb_up_alt_outlined,
          onTap: () => _submit(ref, rating: 5, helpful: true),
        ),
        _FeedbackButton(
          label: 'Missing',
          icon: Icons.playlist_add_rounded,
          onTap: () => _submit(ref, rating: 2, helpful: false, missing: ['context']),
        ),
        _FeedbackButton(
          label: 'Irrelevant',
          icon: Icons.filter_alt_off_outlined,
          onTap: () => _submit(ref, rating: 2, helpful: false, irrelevant: ['context']),
        ),
      ],
    );
  }

  Future<void> _submit(
    WidgetRef ref, {
    int? rating,
    bool? helpful,
    List<String> missing = const [],
    List<String> irrelevant = const [],
  }) async {
    await ref.read(ripClientProvider).submitGatewayFeedback(
          sessionId: sessionId,
          rating: rating,
          wasHelpful: helpful,
          missingContext: missing,
          irrelevantContext: irrelevant,
        );
  }
}

class _FeedbackButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;

  const _FeedbackButton({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      avatar: Icon(icon, size: 14, color: AppColors.textSecondary),
      label: Text(label),
      visualDensity: VisualDensity.compact,
      onPressed: onTap,
    );
  }
}
