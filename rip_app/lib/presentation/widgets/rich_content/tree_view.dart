import 'package:flutter/material.dart';

class TreeNode {
  final String id;
  final String title;
  final List<TreeNode> children;
  final String? iconPath;

  TreeNode({
    required this.id,
    required this.title,
    this.children = const [],
    this.iconPath,
  });
}

class TreeView extends StatefulWidget {
  final TreeNode root;
  final ValueChanged<TreeNode>? onNodeTap;
  final bool initiallyExpanded;

  const TreeView({
    super.key,
    required this.root,
    this.onNodeTap,
    this.initiallyExpanded = true,
  });

  @override
  State<TreeView> createState() => _TreeViewState();
}

class _TreeViewState extends State<TreeView> {
  final Map<String, bool> _expandedNodes = {};

  @override
  void initState() {
    super.initState();
    _initializeExpansion(widget.root);
  }

  void _initializeExpansion(TreeNode node) {
    if (widget.initiallyExpanded) {
      _expandedNodes[node.id] = true;
    }
    for (final child in node.children) {
      _initializeExpansion(child);
    }
  }

  Widget _buildNode(TreeNode node, int level) {
    final isExpanded = _expandedNodes[node.id] ?? false;
    final hasChildren = node.children.isNotEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () {
            setState(() {
              _expandedNodes[node.id] = !isExpanded;
            });
            widget.onNodeTap?.call(node);
          },
          child: Padding(
            padding: EdgeInsets.only(left: level * 16.0 + 8, right: 8, top: 4, bottom: 4),
            child: Row(
              children: [
                if (hasChildren)
                  Icon(
                    isExpanded ? Icons.expand_more : Icons.chevron_right,
                    size: 20,
                  )
                else
                  const SizedBox(width: 20),
                if (node.iconPath != null)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: Icon(node.iconPath == 'function' ? Icons.functions : Icons.code),
                  ),
                Expanded(
                  child: Text(
                    node.title,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (hasChildren && isExpanded)
          ...node.children.map((child) => _buildNode(child, level + 1)),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: _buildNode(widget.root, 0),
    );
  }
}
