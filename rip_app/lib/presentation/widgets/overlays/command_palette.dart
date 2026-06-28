import 'package:flutter/material.dart';
import '../../../utils/command_parser.dart';

class CommandPalette extends StatefulWidget {
  final Function(String) onCommandSubmitted;
  final VoidCallback onDismissed;

  const CommandPalette({
    super.key,
    required this.onCommandSubmitted,
    required this.onDismissed,
  });

  @override
  State<CommandPalette> createState() => _CommandPaletteState();
}

class _CommandPaletteState extends State<CommandPalette> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _focusNode.requestFocus();
    _controller.addListener(() {
      setState(() {
        _filter = _controller.text.toLowerCase();
      });
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _getFilteredCommands() {
    final allCommands = CommandParser.getAvailableCommands();
    if (_filter.isEmpty) {
      return allCommands;
    }
    return allCommands
        .where((cmd) =>
            cmd['name'].toLowerCase().contains(_filter) ||
            cmd['description'].toLowerCase().contains(_filter))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final filteredCommands = _getFilteredCommands();

    return Container(
      height: MediaQuery.of(context).size.height * 0.6,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(16),
          topRight: Radius.circular(16),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'Type / to search commands...',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.search),
              ),
              onSubmitted: (value) {
                if (value.trim().isNotEmpty) {
                  widget.onCommandSubmitted(value);
                  widget.onDismissed();
                }
              },
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: filteredCommands.length,
              itemBuilder: (context, index) {
                final cmd = filteredCommands[index];
                return ListTile(
                  leading: const Icon(Icons.terminal),
                  title: Text(cmd['name']),
                  subtitle: Text(cmd['description']),
                  onTap: () {
                    _controller.text = cmd['name'];
                    widget.onCommandSubmitted(cmd['name']);
                    widget.onDismissed();
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
