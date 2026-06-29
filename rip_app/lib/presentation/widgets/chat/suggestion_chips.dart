import 'package:flutter/material.dart';

import '../../../core/design/app_colors.dart';

class SuggestionChip {
  final String id;
  final String text;
  final String? action;

  SuggestionChip({
    required this.id,
    required this.text,
    this.action,
  });
}

class SuggestionChips extends StatelessWidget {
  final List<SuggestionChip> suggestions;
  final ValueChanged<SuggestionChip> onSelected;

  const SuggestionChips({
    super.key,
    required this.suggestions,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    if (suggestions.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: suggestions.map((suggestion) {
        return ActionChip(
          label: Text(suggestion.text),
          onPressed: () => onSelected(suggestion),
          avatar: const Icon(
            Icons.auto_awesome_rounded,
            size: 16,
            color: AppColors.textPrimary,
          ),
          backgroundColor: Colors.white.withValues(alpha: 0.075),
          side: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          labelStyle: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        );
      }).toList(),
    );
  }
}
