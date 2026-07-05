import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/models/pipeline_trace.dart';
import '../providers/connection_provider.dart';
import '../providers/gateway_provider.dart';
import '../providers/project_provider.dart';
import '../widgets/chat/pipeline_trace_widgets.dart';

class WorkflowsScreen extends ConsumerStatefulWidget {
  const WorkflowsScreen({
    super.key,
    this.initialWorkflowId,
    this.initialRunId,
  });

  final String? initialWorkflowId;
  final String? initialRunId;

  @override
  ConsumerState<WorkflowsScreen> createState() => _WorkflowsScreenState();
}

class _WorkflowsScreenState extends ConsumerState<WorkflowsScreen> {
  Map<String, dynamic>? _selected;
  String? _runId;
  Map<String, dynamic>? _runState;
  Timer? _poller;
  bool _loadedInitialRun = false;
  final _answerController = TextEditingController();

  @override
  void dispose() {
    _poller?.cancel();
    _answerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final workflows = ref.watch(gatewayWorkflowsProvider);
    return Scaffold(
      extendBodyBehindAppBar: true,
      body: workflows.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Workflows unavailable: $error')),
        data: (items) {
          final selected = _selected ?? _initialSelectedWorkflow(items);
          if (selected == null) {
            return _EmptyCanvasBuilder(onCreate: _createWorkflow);
          }
          if (!_loadedInitialRun &&
              widget.initialWorkflowId != null &&
              widget.initialRunId != null) {
            _loadedInitialRun = true;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              _loadInitialRun(selected, widget.initialRunId!);
            });
          }
          return _WorkflowCanvasShell(
            workflow: selected,
            workflows: items,
            runId: _runId,
            runState: _runState,
            answerController: _answerController,
            onBack: () => Navigator.of(context).maybePop(),
            onSwitchWorkflow: () => _showWorkflowSwitcher(items),
            onCreateWorkflow: _createWorkflow,
            onAddBlock: () => _showPalette(selected),
            onPublish: () => _publish(selected),
            onDeleteStep: (stepId) => _deleteStep(selected, stepId),
            onMoveBlock: (stepId, position) => _moveBlock(selected, stepId, position),
            onConnectBlocks: (source, target) => _connectBlocks(selected, source, target),
            onDeleteWire: (wireId) => _deleteWire(selected, wireId),
            onAnswer: () => _answerMissingInput(selected),
            onApprove: () => _approve(selected),
            onReject: () => _reject(selected),
          );
        },
      ),
    );
  }

  Map<String, dynamic>? _initialSelectedWorkflow(List<dynamic> items) {
    if (items.isEmpty) return null;
    if (widget.initialWorkflowId != null) {
      for (final item in items) {
        final workflow = Map<String, dynamic>.from(item as Map);
        final id = workflow['draft_id']?.toString() ?? workflow['workflow_id']?.toString();
        if (id == widget.initialWorkflowId) {
          return workflow;
        }
      }
    }
    return Map<String, dynamic>.from(items.first as Map);
  }

  Future<void> _loadInitialRun(Map<String, dynamic> workflow, String runId) async {
    final workflowId = workflow['draft_id']?.toString() ?? workflow['workflow_id']?.toString();
    if (workflowId == null || !mounted) return;
    final canvas = await ref.read(ripClientProvider).gatewayWorkflowCanvas(draftId: workflowId);
    final state = await ref.read(ripClientProvider).gatewayWorkflowRunState(draftId: workflowId, runId: runId);
    if (!mounted) return;
    setState(() {
      _selected = canvas;
      _runId = runId;
      _runState = state;
    });
    _startPolling(workflowId, runId);
  }

  Future<void> _showWorkflowSwitcher(List<dynamic> items) async {
    final selected = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      showDragHandle: true,
      builder: (context) => _WorkflowList(
        items: items,
        selectedId: _selected?['draft_id']?.toString(),
        onSelect: (item) => Navigator.pop(context, Map<String, dynamic>.from(item as Map)),
      ),
    );
    if (selected == null) return;
    setState(() {
      _selected = selected;
      _runId = null;
      _runState = null;
    });
  }

  Future<void> _createWorkflow() async {
    final nameController = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('New Workflow'),
        content: TextField(
          controller: nameController,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Name'),
          textInputAction: TextInputAction.done,
          onSubmitted: (value) => Navigator.pop(context, value),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(context, nameController.text),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    nameController.dispose();
    if (name == null || name.trim().isEmpty) return;
    final projectId = ref.read(activeProjectIdProvider);
    final created = await ref.read(ripClientProvider).createGatewayWorkflow(
          name: name.trim(),
          projectId: projectId,
        );
    ref.invalidate(gatewayWorkflowsProvider);
    setState(() {
      _selected = created;
    });
  }

  Future<void> _showPalette(Map<String, dynamic> workflow) async {
    final palette = await ref.read(ripClientProvider).gatewayWorkflowPalette();
    if (!mounted) return;
    final blocks = (palette['blocks'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
    final block = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      showDragHandle: true,
      builder: (context) => _BlockPalette(blocks: blocks),
    );
    if (block == null || !mounted) return;
    final configured = await showModalBottomSheet<_ConfiguredBlock>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _BlockConfigSheet(block: block, existingBlocks: _blocks(workflow), ref: ref),
    );
    if (configured == null) return;
    final updated = await ref.read(ripClientProvider).appendGatewayWorkflowBlock(
          draftId: workflow['draft_id'].toString(),
          blockId: block['id'].toString(),
          config: configured.config,
          inputBindings: configured.inputBindings,
          position: _nextBlockPosition(workflow),
        );
    _refreshSelected(updated);
  }

  Future<void> _publish(Map<String, dynamic> workflow) async {
    final updated = await ref.read(ripClientProvider).publishGatewayWorkflow(workflow['draft_id'].toString());
    _refreshSelected({...workflow, 'status': updated['status']});
  }

  void _startPolling(String draftId, String runId) {
    _poller?.cancel();
    _poller = Timer.periodic(const Duration(seconds: 2), (_) async {
      final state = await ref.read(ripClientProvider).gatewayWorkflowRunState(draftId: draftId, runId: runId);
      if (!mounted) return;
      setState(() => _runState = state);
      final statuses = (state['step_states'] as Map? ?? const {})
          .values
          .whereType<Map>()
          .map((step) => step['status']?.toString() ?? '')
          .toSet();
      if (statuses.contains('awaiting_approval') ||
          statuses.contains('failed') ||
          state['final_output'] != null) {
        _poller?.cancel();
      }
    });
  }

  Future<void> _deleteStep(Map<String, dynamic> workflow, String stepId) async {
    final updated = await ref.read(ripClientProvider).deleteGatewayWorkflowBlock(
          draftId: workflow['draft_id'].toString(),
          stepId: stepId,
        );
    _refreshSelected(updated);
  }

  Future<void> _reorder(Map<String, dynamic> workflow, int oldIndex, int newIndex) async {
    final blocks = _blocks(workflow);
    if (newIndex > oldIndex) newIndex -= 1;
    final moved = blocks.removeAt(oldIndex);
    blocks.insert(newIndex, moved);
    final updated = await ref.read(ripClientProvider).reorderGatewayWorkflowBlocks(
          draftId: workflow['draft_id'].toString(),
          stepOrder: blocks.map((block) => block['step_id'].toString()).toList(),
        );
    _refreshSelected(updated);
  }

  Future<void> _moveBlock(Map<String, dynamic> workflow, String stepId, Offset position) async {
    final updated = await ref.read(ripClientProvider).patchGatewayWorkflowBlock(
          draftId: workflow['draft_id'].toString(),
          stepId: stepId,
          position: {'x': position.dx, 'y': position.dy},
        );
    _refreshSelected(updated);
  }

  Future<void> _connectBlocks(Map<String, dynamic> workflow, String sourceStepId, String targetStepId) async {
    await ref.read(ripClientProvider).addGatewayWorkflowWire(
          draftId: workflow['draft_id'].toString(),
          sourceStepId: sourceStepId,
          targetStepId: targetStepId,
          targetPort: _defaultTargetPort(_blocks(workflow), targetStepId),
        );
    final updated = await ref.read(ripClientProvider).gatewayWorkflowCanvas(draftId: workflow['draft_id'].toString());
    _refreshSelected(updated);
  }

  Future<void> _deleteWire(Map<String, dynamic> workflow, String wireId) async {
    final response = await ref.read(ripClientProvider).deleteGatewayWorkflowWire(
          draftId: workflow['draft_id'].toString(),
          wireId: wireId,
        );
    _refreshSelected({...workflow, 'wires': response['wires'] ?? const []});
  }

  Future<void> _answerMissingInput(Map<String, dynamic> workflow) async {
    final missing = _missingStepId(_runState);
    if (missing == null || _runId == null || _answerController.text.trim().isEmpty) return;
    final state = await ref.read(ripClientProvider).answerGatewayWorkflowInput(
          draftId: workflow['draft_id'].toString(),
          runId: _runId!,
          stepId: missing,
          value: _answerController.text.trim(),
        );
    setState(() => _runState = state);
    _answerController.clear();
    _startPolling(workflow['draft_id'].toString(), _runId!);
  }

  Future<void> _approve(Map<String, dynamic> workflow) async {
    if (_runId == null) return;
    final response = await ref.read(ripClientProvider).approveGatewayWorkflowRun(
          draftId: workflow['draft_id'].toString(),
          runId: _runId!,
        );
    setState(() => _runState = Map<String, dynamic>.from(response['state'] as Map? ?? const {}));
    _startPolling(workflow['draft_id'].toString(), _runId!);
  }

  Future<void> _reject(Map<String, dynamic> workflow) async {
    if (_runId == null) return;
    final response = await ref.read(ripClientProvider).rejectGatewayWorkflowRun(
          draftId: workflow['draft_id'].toString(),
          runId: _runId!,
        );
    setState(() => _runState = Map<String, dynamic>.from(response['state'] as Map? ?? const {}));
  }

  void _refreshSelected(Map<String, dynamic> updated) {
    ref.invalidate(gatewayWorkflowsProvider);
    setState(() {
      _selected = {...?_selected, ...updated};
    });
  }
}

class _WorkflowList extends StatelessWidget {
  const _WorkflowList({required this.items, required this.selectedId, required this.onSelect});

  final List<dynamic> items;
  final String? selectedId;
  final ValueChanged<dynamic> onSelect;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Center(child: Text('No workflows yet.'));
    }
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final item = Map<String, dynamic>.from(items[index] as Map);
        final id = item['draft_id']?.toString() ?? '';
        final blocks = item['blocks'] as List? ?? const [];
        return ListTile(
          selected: id == selectedId,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          tileColor: Theme.of(context).colorScheme.surface,
          leading: const Icon(Icons.account_tree_rounded),
          title: Text('${item['name'] ?? 'Workflow'}', overflow: TextOverflow.ellipsis),
          subtitle: Text('${item['status'] ?? 'draft'} - ${blocks.length} blocks'),
          onTap: () {
            HapticFeedback.selectionClick();
            onSelect(item);
          },
        );
      },
    );
  }
}

class _WorkflowCanvasShell extends StatelessWidget {
  const _WorkflowCanvasShell({
    required this.workflow,
    required this.workflows,
    required this.runId,
    required this.runState,
    required this.answerController,
    required this.onBack,
    required this.onSwitchWorkflow,
    required this.onCreateWorkflow,
    required this.onAddBlock,
    required this.onPublish,
    required this.onDeleteStep,
    required this.onMoveBlock,
    required this.onConnectBlocks,
    required this.onDeleteWire,
    required this.onAnswer,
    required this.onApprove,
    required this.onReject,
  });

  final Map<String, dynamic> workflow;
  final List<dynamic> workflows;
  final String? runId;
  final Map<String, dynamic>? runState;
  final TextEditingController answerController;
  final VoidCallback onBack;
  final VoidCallback onSwitchWorkflow;
  final VoidCallback onCreateWorkflow;
  final VoidCallback onAddBlock;
  final VoidCallback onPublish;
  final ValueChanged<String> onDeleteStep;
  final void Function(String stepId, Offset position) onMoveBlock;
  final void Function(String sourceStepId, String targetStepId) onConnectBlocks;
  final ValueChanged<String> onDeleteWire;
  final VoidCallback onAnswer;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final blocks = _blocks(workflow);
    final state = runState;
    final top = MediaQuery.paddingOf(context).top;
    return Stack(
      children: [
        Positioned.fill(
          child: _WorkflowCanvas(
            blocks: blocks,
            wires: _wires(workflow),
            runState: state,
            onMoveBlock: onMoveBlock,
            onConnectBlocks: onConnectBlocks,
            onDeleteBlock: onDeleteStep,
            onDeleteWire: onDeleteWire,
          ),
        ),
        Positioned(
          top: top + 10,
          left: 12,
          right: 12,
          child: _FloatingCanvasHeader(
            title: '${workflow['name'] ?? 'Workflow'}',
            status: '${workflow['status'] ?? 'draft'}',
            blockCount: blocks.length,
            wireCount: _wires(workflow).length,
            onBack: onBack,
            onSwitchWorkflow: onSwitchWorkflow,
            onCreateWorkflow: onCreateWorkflow,
          ),
        ),
        Positioned(
          right: 14,
          bottom: MediaQuery.paddingOf(context).bottom + 18,
          child: _CanvasActionDock(
            canPublish: blocks.isNotEmpty,
            onAddBlock: onAddBlock,
            onPublish: onPublish,
          ),
        ),
        if (state != null)
          Positioned(
            left: 12,
            right: 12,
            bottom: MediaQuery.paddingOf(context).bottom + 92,
            child: _FloatingRunPanel(
              runId: runId,
              state: state,
              answerController: answerController,
              onAnswer: onAnswer,
              onApprove: onApprove,
              onReject: onReject,
            ),
          ),
      ],
    );
  }
}

class _FloatingCanvasHeader extends StatelessWidget {
  const _FloatingCanvasHeader({
    required this.title,
    required this.status,
    required this.blockCount,
    required this.wireCount,
    required this.onBack,
    required this.onSwitchWorkflow,
    required this.onCreateWorkflow,
  });

  final String title;
  final String status;
  final int blockCount;
  final int wireCount;
  final VoidCallback onBack;
  final VoidCallback onSwitchWorkflow;
  final VoidCallback onCreateWorkflow;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: colorScheme.surface.withValues(alpha: 0.92),
      elevation: 10,
      shadowColor: Colors.black.withValues(alpha: 0.2),
      borderRadius: BorderRadius.circular(18),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
        child: Row(
          children: [
            IconButton(
              tooltip: 'Back',
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back_rounded),
            ),
            Expanded(
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: onSwitchWorkflow,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium),
                      Text('$status - $blockCount blocks - $wireCount wires', maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.labelSmall),
                    ],
                  ),
                ),
              ),
            ),
            IconButton(
              tooltip: 'Switch workflow',
              onPressed: onSwitchWorkflow,
              icon: const Icon(Icons.keyboard_arrow_down_rounded),
            ),
            IconButton(
              tooltip: 'New workflow',
              onPressed: onCreateWorkflow,
              icon: const Icon(Icons.add_rounded),
            ),
          ],
        ),
      ),
    );
  }
}

class _CanvasActionDock extends StatelessWidget {
  const _CanvasActionDock({
    required this.canPublish,
    required this.onAddBlock,
    required this.onPublish,
  });

  final bool canPublish;
  final VoidCallback onAddBlock;
  final VoidCallback onPublish;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        FloatingActionButton.small(
          heroTag: 'publish_workflow',
          tooltip: 'Publish',
          onPressed: canPublish ? onPublish : null,
          child: const Icon(Icons.publish_rounded),
        ),
        const SizedBox(height: 10),
        FloatingActionButton(
          heroTag: 'add_workflow_block',
          tooltip: 'Add block',
          onPressed: onAddBlock,
          child: const Icon(Icons.add_rounded),
        ),
      ],
    );
  }
}

class _FloatingRunPanel extends StatelessWidget {
  const _FloatingRunPanel({
    required this.runId,
    required this.state,
    required this.answerController,
    required this.onAnswer,
    required this.onApprove,
    required this.onReject,
  });

  final String? runId;
  final Map<String, dynamic> state;
  final TextEditingController answerController;
  final VoidCallback onAnswer;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.94),
      elevation: 12,
      borderRadius: BorderRadius.circular(16),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: _RunStatePanel(
          runId: runId,
          state: state,
          answerController: answerController,
          onAnswer: onAnswer,
          onApprove: onApprove,
          onReject: onReject,
        ),
      ),
    );
  }
}

class _EmptyCanvasBuilder extends StatelessWidget {
  const _EmptyCanvasBuilder({required this.onCreate});

  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const Positioned.fill(child: ColoredBox(color: Colors.black12)),
        Center(
          child: FilledButton.icon(
            onPressed: onCreate,
            icon: const Icon(Icons.add_rounded),
            label: const Text('Create workflow'),
          ),
        ),
      ],
    );
  }
}

class _RunStatePanel extends StatelessWidget {
  const _RunStatePanel({
    required this.runId,
    required this.state,
    required this.answerController,
    required this.onAnswer,
    required this.onApprove,
    required this.onReject,
  });

  final String? runId;
  final Map<String, dynamic> state;
  final TextEditingController answerController;
  final VoidCallback onAnswer;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final trace = _traceFromRunState(runId ?? '', state);
    final awaitingApproval = _hasStepStatus(state, 'awaiting_approval');
    final missingStep = _missingStepId(state);
    final complete = state['final_output'] != null || _hasStepStatus(state, 'failed');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        complete ? PipelineSummaryChip(trace: trace) : PipelineStepList(trace: trace),
        if (missingStep != null) ...[
          const SizedBox(height: 12),
          TextField(
            controller: answerController,
            decoration: InputDecoration(
              labelText: 'Missing input',
              suffixIcon: IconButton(
                tooltip: 'Submit',
                icon: const Icon(Icons.send_rounded),
                onPressed: onAnswer,
              ),
            ),
          ),
        ],
        if (awaitingApproval) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: onApprove,
                  icon: const Icon(Icons.check_rounded),
                  label: const Text('Approve'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onReject,
                  icon: const Icon(Icons.close_rounded),
                  label: const Text('Reject'),
                ),
              ),
            ],
          ),
        ],
        if (state['final_output'] != null) ...[
          const SizedBox(height: 12),
          SelectableText('${state['final_output']}'),
        ],
      ],
    );
  }
}

class _WorkflowCanvas extends StatefulWidget {
  const _WorkflowCanvas({
    required this.blocks,
    required this.wires,
    required this.runState,
    required this.onMoveBlock,
    required this.onConnectBlocks,
    required this.onDeleteBlock,
    required this.onDeleteWire,
  });

  final List<Map<String, dynamic>> blocks;
  final List<Map<String, dynamic>> wires;
  final Map<String, dynamic>? runState;
  final void Function(String stepId, Offset position) onMoveBlock;
  final void Function(String sourceStepId, String targetStepId) onConnectBlocks;
  final ValueChanged<String> onDeleteBlock;
  final ValueChanged<String> onDeleteWire;

  @override
  State<_WorkflowCanvas> createState() => _WorkflowCanvasState();
}

class _WorkflowCanvasState extends State<_WorkflowCanvas> {
  static const _canvasSize = Size(18000, 12000);
  static const _blockSize = Size(230, 150);

  String? _selectedStepId;
  String? _wireSourceStepId;
  String? _selectedWireId;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return ColoredBox(
      color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.35),
      child: Stack(
          children: [
            InteractiveViewer(
              minScale: 0.35,
              maxScale: 2.4,
              boundaryMargin: const EdgeInsets.all(2600),
              constrained: false,
              child: SizedBox(
                width: _canvasSize.width,
                height: _canvasSize.height,
                child: Stack(
                  children: [
                    Positioned(
                      left: 80,
                      top: 220,
                      child: _CanvasEndpoint(
                        icon: Icons.login_rounded,
                        title: 'ENTRY',
                        subtitle: 'Chat trigger',
                        color: colorScheme.primary,
                      ),
                    ),
                    Positioned(
                      left: _canvasSize.width - 340,
                      top: 220,
                      child: _CanvasEndpoint(
                        icon: Icons.logout_rounded,
                        title: 'EXIT',
                        subtitle: 'Chat response',
                        color: const Color(0xFF22C55E),
                      ),
                    ),
                    GestureDetector(
                      behavior: HitTestBehavior.translucent,
                      onTapDown: (details) => _selectWireAt(details.localPosition),
                      child: CustomPaint(
                        size: _canvasSize,
                        painter: _WirePainter(
                          blocks: widget.blocks,
                          wires: widget.wires,
                          runState: widget.runState,
                          colorScheme: colorScheme,
                          selectedWireId: _selectedWireId,
                        ),
                      ),
                    ),
                    for (final block in widget.blocks)
                      _CanvasBlockCard(
                        block: block,
                        status: _stepStatus(widget.runState, block['step_id']?.toString()),
                        selected: block['step_id']?.toString() == _selectedStepId,
                        wireSource: block['step_id']?.toString() == _wireSourceStepId,
                        onSelected: () {
                          setState(() {
                            _selectedStepId = block['step_id']?.toString();
                            _selectedWireId = null;
                          });
                          _showBlockDetails(block);
                        },
                        onDrag: (position) => setState(() {
                          block['position'] = {
                            'x': position.dx.clamp(80, _canvasSize.width - _blockSize.width - 240),
                            'y': position.dy.clamp(120, _canvasSize.height - _blockSize.height - 240),
                          };
                        }),
                        onMove: widget.onMoveBlock,
                        onDelete: widget.onDeleteBlock,
                        onDeleteConnectedWires: _deleteConnectedWires,
                        onWireTap: _handleWireTap,
                      ),
                  ],
                ),
              ),
            ),
            if (_wireSourceStepId != null)
              Positioned(
                left: 12,
                right: 12,
                bottom: 12,
                child: Material(
                  color: colorScheme.inverseSurface,
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Tap another block to connect from $_wireSourceStepId',
                            style: TextStyle(color: colorScheme.onInverseSurface),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Cancel connection',
                          onPressed: () => setState(() => _wireSourceStepId = null),
                          icon: Icon(Icons.close_rounded, color: colorScheme.onInverseSurface),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (_selectedWireId != null)
              Positioned(
                left: 12,
                right: 12,
                bottom: _wireSourceStepId == null ? 12 : 78,
                child: _SelectedWireBar(
                  wire: widget.wires.firstWhere(
                    (wire) => wire['id']?.toString() == _selectedWireId,
                    orElse: () => const <String, dynamic>{},
                  ),
                  onDelete: () {
                    final wireId = _selectedWireId;
                    if (wireId != null) {
                      widget.onDeleteWire(wireId);
                    }
                    setState(() => _selectedWireId = null);
                  },
                  onClear: () => setState(() => _selectedWireId = null),
                ),
              ),
          ],
        ),
    );
  }

  void _selectWireAt(Offset point) {
    for (final wire in widget.wires.reversed) {
      final source = _blockForStep(wire['source_step_id']?.toString());
      final target = _blockForStep(wire['target_step_id']?.toString());
      if (source == null || target == null) continue;
      final sourcePos = _blockPosition(source) + Offset(_blockSize.width, 108);
      final targetPos = _blockPosition(target) + const Offset(0, 108);
      if (_pointNearWire(point, sourcePos, targetPos)) {
        setState(() {
          _selectedWireId = wire['id']?.toString();
          _selectedStepId = null;
          _wireSourceStepId = null;
        });
        return;
      }
    }
    setState(() => _selectedWireId = null);
  }

  Map<String, dynamic>? _blockForStep(String? stepId) {
    if (stepId == null) return null;
    for (final block in widget.blocks) {
      if (block['step_id']?.toString() == stepId) {
        return block;
      }
    }
    return null;
  }

  bool _pointNearWire(Offset point, Offset source, Offset target) {
    for (var i = 0; i <= 20; i++) {
      final t = i / 20;
      final sample = Offset(
        _cubic(source.dx, source.dx + 110, target.dx - 110, target.dx, t),
        _cubic(source.dy, source.dy, target.dy, target.dy, t),
      );
      if ((sample - point).distance <= 24) return true;
    }
    return false;
  }

  double _cubic(double a, double b, double c, double d, double t) {
    final mt = 1 - t;
    return mt * mt * mt * a + 3 * mt * mt * t * b + 3 * mt * t * t * c + t * t * t * d;
  }

  void _handleWireTap(String stepId) {
    final source = _wireSourceStepId;
    if (source == null) {
      setState(() => _wireSourceStepId = stepId);
      return;
    }
    if (source != stepId) {
      widget.onConnectBlocks(source, stepId);
    }
    setState(() => _wireSourceStepId = null);
  }

  void _deleteConnectedWires(String stepId) {
    for (final wire in widget.wires) {
      final isConnected = wire['source_step_id']?.toString() == stepId ||
          wire['target_step_id']?.toString() == stepId;
      final wireId = wire['id']?.toString();
      if (isConnected && wireId != null) {
        widget.onDeleteWire(wireId);
      }
    }
  }

  void _showBlockDetails(Map<String, dynamic> block) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => _BlockDetailsSheet(
        block: block,
        status: _stepStatus(widget.runState, block['step_id']?.toString()),
        output: _stepOutput(widget.runState, block['step_id']?.toString()),
        connectedWires: widget.wires
            .where((wire) =>
                wire['source_step_id']?.toString() == block['step_id']?.toString() ||
                wire['target_step_id']?.toString() == block['step_id']?.toString())
            .map((wire) => Map<String, dynamic>.from(wire))
            .toList(),
        onConnect: () {
          Navigator.pop(context);
          _handleWireTap(block['step_id']?.toString() ?? '');
        },
        onDeleteWires: () {
          Navigator.pop(context);
          _deleteConnectedWires(block['step_id']?.toString() ?? '');
        },
        onDeleteBlock: () {
          Navigator.pop(context);
          widget.onDeleteBlock(block['step_id']?.toString() ?? '');
        },
      ),
    );
  }
}

class _CanvasBlockCard extends StatelessWidget {
  const _CanvasBlockCard({
    required this.block,
    required this.status,
    required this.selected,
    required this.wireSource,
    required this.onSelected,
    required this.onDrag,
    required this.onMove,
    required this.onDelete,
    required this.onDeleteConnectedWires,
    required this.onWireTap,
  });

  final Map<String, dynamic> block;
  final String status;
  final bool selected;
  final bool wireSource;
  final VoidCallback onSelected;
  final ValueChanged<Offset> onDrag;
  final void Function(String stepId, Offset position) onMove;
  final ValueChanged<String> onDelete;
  final ValueChanged<String> onDeleteConnectedWires;
  final ValueChanged<String> onWireTap;

  @override
  Widget build(BuildContext context) {
    final stepId = block['step_id']?.toString() ?? '';
    final position = _blockPosition(block);
    final colorScheme = Theme.of(context).colorScheme;
    final statusColor = _statusColor(colorScheme, status);
    return Positioned(
      left: position.dx,
      top: position.dy,
      width: 230,
      height: 150,
      child: GestureDetector(
        onTap: onSelected,
        onPanEnd: (_) => onMove(stepId, _blockPosition(block)),
        onPanUpdate: (details) {
          final current = _blockPosition(block);
          onDrag(current + details.delta);
        },
        child: Material(
          color: colorScheme.surface,
          elevation: selected || wireSource ? 6 : 1,
          borderRadius: BorderRadius.circular(8),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: wireSource ? colorScheme.primary : selected ? statusColor : colorScheme.outlineVariant,
                width: selected || wireSource ? 2 : 1,
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(_iconForBlock(block), size: 18, color: statusColor),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          block['display_name']?.toString().isNotEmpty == true
                              ? block['display_name'].toString()
                              : block['block_id']?.toString() ?? 'Block',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                      ),
                      PopupMenuButton<String>(
                        padding: EdgeInsets.zero,
                        icon: const Icon(Icons.more_horiz_rounded, size: 18),
                        onSelected: (value) {
                          if (value == 'delete') onDelete(stepId);
                          if (value == 'delete_wires') onDeleteConnectedWires(stepId);
                          if (value == 'wire') onWireTap(stepId);
                        },
                        itemBuilder: (context) => const [
                          PopupMenuItem(value: 'wire', child: Text('Connect')),
                          PopupMenuItem(value: 'delete_wires', child: Text('Delete wires')),
                          PopupMenuItem(value: 'delete', child: Text('Delete')),
                        ],
                      ),
                    ],
                  ),
                  const Divider(height: 14),
                  Row(
                    children: [
                      _PortDot(color: colorScheme.primary),
                      const SizedBox(width: 6),
                      Text('ENTRY', style: Theme.of(context).textTheme.labelSmall),
                      const Spacer(),
                      Text('EXIT', style: Theme.of(context).textTheme.labelSmall),
                      const SizedBox(width: 6),
                      InkWell(
                        borderRadius: BorderRadius.circular(14),
                        onTap: () => onWireTap(stepId),
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: _PortDot(color: statusColor),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _bindingPreview(block),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const Spacer(),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          status,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(color: statusColor),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _WirePainter extends CustomPainter {
  const _WirePainter({
    required this.blocks,
    required this.wires,
    required this.runState,
    required this.colorScheme,
    required this.selectedWireId,
  });

  final List<Map<String, dynamic>> blocks;
  final List<Map<String, dynamic>> wires;
  final Map<String, dynamic>? runState;
  final ColorScheme colorScheme;
  final String? selectedWireId;

  @override
  void paint(Canvas canvas, Size size) {
    final blockByStep = {
      for (final block in blocks) block['step_id']?.toString(): block,
    };
    for (final wire in wires) {
      final source = blockByStep[wire['source_step_id']?.toString()];
      final target = blockByStep[wire['target_step_id']?.toString()];
      if (source == null || target == null) continue;
      final sourcePos = _blockPosition(source) + const Offset(230, 108);
      final targetPos = _blockPosition(target) + const Offset(0, 108);
      final path = Path()
        ..moveTo(sourcePos.dx, sourcePos.dy)
        ..cubicTo(
          sourcePos.dx + 90,
          sourcePos.dy,
          targetPos.dx - 90,
          targetPos.dy,
          targetPos.dx,
          targetPos.dy,
        );
      final status = _stepStatus(runState, wire['target_step_id']?.toString());
      final selected = wire['id']?.toString() == selectedWireId;
      final paint = Paint()
        ..color = _statusColor(colorScheme, status).withValues(alpha: 0.82)
        ..strokeWidth = selected ? 5 : status == 'running' ? 3.4 : 2.2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round;
      canvas.drawPath(path, paint);
      if (selected) {
        canvas.drawCircle(
          Offset.lerp(sourcePos, targetPos, 0.5)!,
          7,
          Paint()..color = colorScheme.primary,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _WirePainter oldDelegate) {
    return oldDelegate.blocks != blocks ||
        oldDelegate.wires != wires ||
        oldDelegate.runState != runState ||
        oldDelegate.selectedWireId != selectedWireId;
  }
}

class _CanvasEndpoint extends StatelessWidget {
  const _CanvasEndpoint({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.92),
      elevation: 8,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: 170,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.8), width: 1.4),
        ),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(title, style: Theme.of(context).textTheme.labelLarge?.copyWith(color: color)),
                  Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SelectedWireBar extends StatelessWidget {
  const _SelectedWireBar({
    required this.wire,
    required this.onDelete,
    required this.onClear,
  });

  final Map<String, dynamic> wire;
  final VoidCallback onDelete;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: colorScheme.surface.withValues(alpha: 0.95),
      elevation: 10,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          children: [
            const Icon(Icons.cable_rounded, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '${wire['source_step_id'] ?? 'source'} -> ${wire['target_step_id'] ?? 'target'}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            IconButton(
              tooltip: 'Disconnect wire',
              onPressed: onDelete,
              icon: const Icon(Icons.link_off_rounded),
            ),
            IconButton(
              tooltip: 'Close',
              onPressed: onClear,
              icon: const Icon(Icons.close_rounded),
            ),
          ],
        ),
      ),
    );
  }
}

class _BlockDetailsSheet extends StatelessWidget {
  const _BlockDetailsSheet({
    required this.block,
    required this.status,
    required this.output,
    required this.connectedWires,
    required this.onConnect,
    required this.onDeleteWires,
    required this.onDeleteBlock,
  });

  final Map<String, dynamic> block;
  final String status;
  final Map<String, dynamic>? output;
  final List<Map<String, dynamic>> connectedWires;
  final VoidCallback onConnect;
  final VoidCallback onDeleteWires;
  final VoidCallback onDeleteBlock;

  @override
  Widget build(BuildContext context) {
    final blockId = block['block_id']?.toString() ?? 'Block';
    final stepId = block['step_id']?.toString() ?? 'step';
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 18),
      child: ListView(
        shrinkWrap: true,
        children: [
          Row(
            children: [
              Icon(_iconForBlock(block), color: _statusColor(Theme.of(context).colorScheme, status)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  block['display_name']?.toString().isNotEmpty == true ? block['display_name'].toString() : blockId,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text('$stepId - $status', style: Theme.of(context).textTheme.labelMedium),
          const Divider(height: 24),
          _DetailSection(title: 'Tools', values: [
            'Connect from this block',
            'Disconnect ${connectedWires.length} wire${connectedWires.length == 1 ? '' : 's'}',
            'Delete block',
          ]),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(onPressed: onConnect, icon: const Icon(Icons.cable_rounded), label: const Text('Connect')),
              OutlinedButton.icon(onPressed: connectedWires.isEmpty ? null : onDeleteWires, icon: const Icon(Icons.link_off_rounded), label: const Text('Disconnect')),
              OutlinedButton.icon(onPressed: onDeleteBlock, icon: const Icon(Icons.delete_outline_rounded), label: const Text('Delete')),
            ],
          ),
          const SizedBox(height: 18),
          _DetailSection(title: 'Input bindings', values: _mapLines(block['input_bindings'])),
          _DetailSection(title: 'Config', values: _mapLines(block['config'])),
          if (connectedWires.isNotEmpty)
            _DetailSection(
              title: 'Connected wires',
              values: connectedWires
                  .map((wire) => '${wire['source_step_id'] ?? 'source'} -> ${wire['target_step_id'] ?? 'target'}:${wire['target_port'] ?? 'input'}')
                  .toList(),
            ),
          if (output != null) _DetailSection(title: 'Last output', values: _mapLines(output)),
        ],
      ),
    );
  }
}

class _DetailSection extends StatelessWidget {
  const _DetailSection({required this.title, required this.values});

  final String title;
  final List<String> values;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          if (values.isEmpty)
            Text('None', style: Theme.of(context).textTheme.bodySmall)
          else
            for (final value in values)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: SelectableText(value, style: Theme.of(context).textTheme.bodySmall),
              ),
        ],
      ),
    );
  }
}

class _CanvasChip extends StatelessWidget {
  const _CanvasChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16),
            const SizedBox(width: 6),
            Text(label, style: Theme.of(context).textTheme.labelMedium),
          ],
        ),
      ),
    );
  }
}

class _PortDot extends StatelessWidget {
  const _PortDot({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: const SizedBox.square(dimension: 10),
    );
  }
}

class _BlockPalette extends StatelessWidget {
  const _BlockPalette({required this.blocks});

  final List<Map<String, dynamic>> blocks;

  @override
  Widget build(BuildContext context) {
    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final block in blocks) {
      final kind = block['kind']?.toString() ?? 'custom';
      grouped.putIfAbsent(kind, () => []).add(block);
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        for (final entry in grouped.entries) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text(_groupTitle(entry.key), style: Theme.of(context).textTheme.titleSmall),
          ),
          for (final block in entry.value)
            ListTile(
              leading: Icon(_iconForKind(entry.key)),
              title: Text('${block['name'] ?? block['id']}'),
              subtitle: Text('${block['description'] ?? block['id']}'),
              onTap: () => Navigator.pop(context, block),
            ),
        ],
      ],
    );
  }
}

class _BlockConfigSheet extends StatefulWidget {
  const _BlockConfigSheet({required this.block, required this.existingBlocks, required this.ref});

  final Map<String, dynamic> block;
  final List<Map<String, dynamic>> existingBlocks;
  final WidgetRef ref;

  @override
  State<_BlockConfigSheet> createState() => _BlockConfigSheetState();
}

class _BlockConfigSheetState extends State<_BlockConfigSheet> {
  final _literalController = TextEditingController();
  final _configController = TextEditingController();
  String _bindingSource = 'trigger_query';
  String? _sourceStepId;
  String? _promptId;

  @override
  void dispose() {
    _literalController.dispose();
    _configController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final blockId = widget.block['id']?.toString() ?? '';
    final isPrompt = blockId == 'prompt.ask_ai';
    final prompts = isPrompt ? widget.ref.watch(gatewayPromptTemplatesProvider) : null;
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 16,
      ),
      child: ListView(
        shrinkWrap: true,
        children: [
          Text('${widget.block['name'] ?? blockId}', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'trigger_query', label: Text('Query')),
              ButtonSegment(value: 'step_output', label: Text('Step')),
              ButtonSegment(value: 'literal', label: Text('Literal')),
            ],
            selected: {_bindingSource},
            onSelectionChanged: (value) => setState(() => _bindingSource = value.first),
          ),
          if (_bindingSource == 'step_output')
            DropdownButtonFormField<String>(
              value: _sourceStepId,
              decoration: const InputDecoration(labelText: 'From step'),
              items: [
                for (final block in widget.existingBlocks)
                  DropdownMenuItem(
                    value: block['step_id']?.toString(),
                    child: Text('${block['step_id']} - ${block['block_id']}'),
                  ),
              ],
              onChanged: (value) => setState(() => _sourceStepId = value),
            ),
          if (_bindingSource == 'literal')
            TextField(
              controller: _literalController,
              decoration: const InputDecoration(labelText: 'Literal value'),
            ),
          if (isPrompt)
            prompts!.when(
              data: (data) {
                final templates = (data['templates'] as List? ?? const []).whereType<Map>().toList();
                return DropdownButtonFormField<String>(
                  value: _promptId,
                  decoration: const InputDecoration(labelText: 'Prompt template'),
                  items: [
                    for (final template in templates)
                      DropdownMenuItem(
                        value: template['id']?.toString(),
                        child: Text('${template['name'] ?? template['id']}'),
                      ),
                  ],
                  onChanged: (value) => setState(() => _promptId = value),
                );
              },
              loading: () => const LinearProgressIndicator(),
              error: (error, _) => Text('Prompt templates unavailable: $error'),
            ),
          TextField(
            controller: _configController,
            minLines: 1,
            maxLines: 3,
            decoration: const InputDecoration(labelText: 'Config note'),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: !isPrompt || (_promptId != null && _promptId!.isNotEmpty)
                ? () => Navigator.pop(context, _buildConfig(blockId))
                : null,
            icon: const Icon(Icons.check_rounded),
            label: const Text('Add Block'),
          ),
          if (isPrompt && (_promptId == null || _promptId!.isEmpty))
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                'Select a prompt template before adding this block.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }

  _ConfiguredBlock _buildConfig(String blockId) {
    final inputKey = blockId == 'terminal.run_tests'
        ? 'command'
        : blockId == 'workflow.approval'
            ? 'title'
            : blockId == 'prompt.ask_ai'
                ? 'variables'
                : 'query';
    final binding = switch (_bindingSource) {
      'literal' => {'source': 'literal', 'value': _literalController.text},
      'step_output' => {'source': 'step_output', 'step_id': _sourceStepId, 'field': 'content'},
      _ => {'source': 'trigger_query'},
    };
    final inputBindings = <String, dynamic>{inputKey: binding};
    if (blockId == 'prompt.ask_ai') {
      inputBindings['prompt_id'] = {'source': 'literal', 'value': _promptId};
    }
    return _ConfiguredBlock(
      config: {
        if (_configController.text.trim().isNotEmpty) 'note': _configController.text.trim(),
      },
      inputBindings: inputBindings,
    );
  }
}

class _ConfiguredBlock {
  const _ConfiguredBlock({required this.config, required this.inputBindings});

  final Map<String, dynamic> config;
  final Map<String, dynamic> inputBindings;
}

class _EmptyWorkflowDetail extends StatelessWidget {
  const _EmptyWorkflowDetail();

  @override
  Widget build(BuildContext context) {
    return const Center(child: Text('Select or create a workflow.'));
  }
}

List<Map<String, dynamic>> _blocks(Map<String, dynamic> workflow) {
  return (workflow['blocks'] as List? ?? const [])
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

List<Map<String, dynamic>> _wires(Map<String, dynamic> workflow) {
  return (workflow['wires'] as List? ?? const [])
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

Offset _blockPosition(Map<String, dynamic> block) {
  final position = block['position'] as Map?;
  final x = position?['x'];
  final y = position?['y'];
  return Offset(
    x is num ? x.toDouble() : 120,
    y is num ? y.toDouble() : 180,
  );
}

Map<String, double> _nextBlockPosition(Map<String, dynamic> workflow) {
  final blocks = _blocks(workflow);
  if (blocks.isEmpty) {
    return const {'x': 160, 'y': 220};
  }
  final positions = blocks.map(_blockPosition).toList();
  final rightMost = positions.reduce((a, b) => a.dx >= b.dx ? a : b);
  final nextX = rightMost.dx + 260;
  final nextY = rightMost.dy;
  if (nextX <= 17200) {
    return {'x': nextX, 'y': nextY};
  }
  final lowestY = positions.map((offset) => offset.dy).reduce((a, b) => a > b ? a : b);
  return {'x': 160, 'y': lowestY + 190};
}

String _stepStatus(Map<String, dynamic>? state, String? stepId) {
  if (stepId == null) return 'ready';
  final stepStates = state?['step_states'] as Map?;
  final step = stepStates?[stepId] as Map?;
  return step?['status']?.toString() ?? 'ready';
}

Map<String, dynamic>? _stepOutput(Map<String, dynamic>? state, String? stepId) {
  if (stepId == null) return null;
  final stepStates = state?['step_states'] as Map?;
  final step = stepStates?[stepId] as Map?;
  final output = step?['output'];
  if (output is Map<String, dynamic>) return output;
  if (output is Map) return Map<String, dynamic>.from(output);
  return null;
}

List<String> _mapLines(Object? value) {
  if (value == null) return const [];
  if (value is Map) {
    if (value.isEmpty) return const [];
    return value.entries
        .map((entry) => '${entry.key}: ${entry.value}')
        .toList();
  }
  if (value is List) {
    if (value.isEmpty) return const [];
    return value.map((item) => '$item').toList();
  }
  return ['$value'];
}

Color _statusColor(ColorScheme colorScheme, String status) {
  return switch (status) {
    'running' => colorScheme.primary,
    'completed' => const Color(0xFF22C55E),
    'failed' => colorScheme.error,
    'awaiting_input' || 'awaiting_approval' => const Color(0xFFF59E0B),
    'skipped' || 'disabled' => colorScheme.outline,
    _ => colorScheme.onSurfaceVariant,
  };
}

IconData _iconForBlock(Map<String, dynamic> block) {
  final blockId = block['block_id']?.toString() ?? '';
  if (blockId.contains('approval')) return Icons.verified_user_rounded;
  if (blockId.contains('terminal')) return Icons.checklist_rounded;
  if (blockId.contains('github')) return Icons.call_merge_rounded;
  if (blockId.contains('prompt')) return Icons.psychology_rounded;
  if (blockId.contains('context') || blockId.contains('rip')) return Icons.search_rounded;
  if (blockId.contains('tool')) return Icons.extension_rounded;
  return Icons.widgets_rounded;
}

String _bindingPreview(Map<String, dynamic> block) {
  final bindings = block['input_bindings'] as Map? ?? const {};
  if (bindings.isEmpty) return 'No inputs configured';
  final parts = <String>[];
  for (final entry in bindings.entries.take(2)) {
    final value = entry.value;
    if (value is Map) {
      parts.add('${entry.key}: ${value['source'] ?? 'input'}');
    } else {
      parts.add('${entry.key}: input');
    }
  }
  return parts.join('\n');
}

String _defaultTargetPort(List<Map<String, dynamic>> blocks, String targetStepId) {
  final target = blocks.cast<Map<String, dynamic>?>().firstWhere(
        (block) => block?['step_id']?.toString() == targetStepId,
        orElse: () => null,
      );
  final blockId = target?['block_id']?.toString() ?? '';
  return blockId == 'terminal.run_tests'
      ? 'command'
      : blockId == 'workflow.approval'
          ? 'title'
          : blockId == 'prompt.ask_ai'
              ? 'variables'
              : 'query';
}

PipelineTrace _traceFromRunState(String runId, Map<String, dynamic> state) {
  final steps = (state['step_states'] as Map? ?? const {}).values.whereType<Map>().toList();
  var seq = 0;
  final events = <PipelineEvent>[
    for (final step in steps)
      PipelineEvent(
        sessionId: runId,
        stage: step['block_id']?.toString() ?? 'workflow_step',
        status: _eventStatus(step['status']?.toString() ?? 'pending'),
        detail: '${step['block_id'] ?? 'Step'}: ${step['status'] ?? 'pending'}',
        meta: {
          if (step['error'] != null) 'error': step['error'],
        },
        seq: ++seq,
        timestamp: DateTime.tryParse(step['completed_at']?.toString() ?? '') ?? DateTime.now(),
      ),
    if (state['final_output'] != null)
      PipelineEvent(
        sessionId: runId,
        stage: 'done',
        status: 'done',
        detail: 'Workflow completed',
        meta: const {},
        seq: ++seq,
        timestamp: DateTime.now(),
      ),
  ];
  return PipelineTrace(sessionId: runId, events: events);
}

String _eventStatus(String status) {
  return status == 'completed' ? 'done' : status;
}

bool _hasStepStatus(Map<String, dynamic>? state, String status) {
  return (state?['step_states'] as Map? ?? const {})
      .values
      .whereType<Map>()
      .any((step) => step['status'] == status);
}

String? _missingStepId(Map<String, dynamic>? state) {
  final missing = state?['missing_inputs'] as Map?;
  if (missing == null || missing.isEmpty) return null;
  return missing.keys.first.toString();
}

String _groupTitle(String kind) {
  return switch (kind) {
    'approval' => 'Approval',
    'verification' => 'Verification',
    'deployment' => 'Deployment',
    'prompt' => 'Prompt + AI',
    'retrieval' => 'Retrieval',
    'tool' => 'Tools',
    _ => 'Custom',
  };
}

IconData _iconForKind(String kind) {
  return switch (kind) {
    'approval' => Icons.verified_user_rounded,
    'verification' => Icons.checklist_rounded,
    'deployment' => Icons.call_merge_rounded,
    'prompt' => Icons.psychology_rounded,
    'retrieval' => Icons.search_rounded,
    'tool' => Icons.extension_rounded,
    _ => Icons.widgets_rounded,
  };
}
