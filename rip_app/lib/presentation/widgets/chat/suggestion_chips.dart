import 'package:flutter/material.dart';

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
          avatar: const Icon(Icons.lightbulb_outline, size: 16),
        );
      }).toList(),
    );
  }
}
