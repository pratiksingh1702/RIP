import 'dart:async';
import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/design/design.dart';
import '../../data/models/pipeline_trace.dart';
import '../providers/connection_provider.dart';
import '../providers/gateway_provider.dart';
import '../providers/project_provider.dart';
import '../widgets/chat/pipeline_trace_widgets.dart';

// ============================================================
// MAIN SCREEN - WorkflowsScreen
// ============================================================

class WorkflowsScreen extends ConsumerStatefulWidget {
  const WorkflowsScreen({super.key, this.initialWorkflowId, this.initialRunId});
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
  final _runQueryController = TextEditingController();
  final List<Map<String, dynamic>> _undoStack = [];
  final List<Map<String, dynamic>> _redoStack = [];
  final Set<String> _selectedBlockIds = {};
  List<Map<String, dynamic>>? _clipboard;
  bool _wireMode = false;
  bool _showGrid = true;
  bool _showMinimap = true;
  bool _snapToGrid = false;
  double _gridSize = 20;
  String? _wireSourceId;
  String? _wireSourcePort;

  @override
  void dispose() {
    _poller?.cancel();
    _answerController.dispose();
    _runQueryController.dispose();
    super.dispose();
  }

  void _pushUndo() {
    if (_selected == null) return;
    _undoStack.add(Map<String, dynamic>.from(_selected!));
    if (_undoStack.length > 50) _undoStack.removeAt(0);
    _redoStack.clear();
  }

  void _undo() {
    if (_undoStack.isEmpty || _selected == null) return;
    _redoStack.add(Map<String, dynamic>.from(_selected!));
    _refresh(_undoStack.removeLast());
  }

  void _redo() {
    if (_redoStack.isEmpty || _selected == null) return;
    _undoStack.add(Map<String, dynamic>.from(_selected!));
    _refresh(_redoStack.removeLast());
  }

  Map<String, dynamic>? _initialSelected(List<dynamic> items) {
    if (items.isEmpty) return null;
    if (widget.initialWorkflowId != null) {
      for (final item in items) {
        final w = Map<String, dynamic>.from(item as Map);
        if ((w['draft_id'] ?? w['workflow_id'])?.toString() ==
            widget.initialWorkflowId) return w;
      }
    }
    return Map<String, dynamic>.from(items.first as Map);
  }
// Replace _handleBlockTap (around line 95-110)
void _handleBlockTap(String stepId, {bool isOutputTap = false, String? outputPort}) {
  if (_wireMode) {
    if (isOutputTap) {
      setState(() {
        if (_wireSourceId == stepId && _wireSourcePort == (outputPort ?? 'output')) {
          _wireSourceId = null;
          _wireSourcePort = null;
        } else {
          _wireSourceId = stepId;
          _wireSourcePort = outputPort ?? 'output';
        }
      });
    } else {
      if (_wireSourceId != null && _wireSourceId != stepId) {
        _showPortPicker(_wireSourceId!, stepId, _wireSourcePort ?? 'output');
      }
    }
    return;
  }
  setState(() {
    _selectedBlockIds.clear();
    _selectedBlockIds.add(stepId);
  });
}

Future<void> _showPortPicker(String sourceStepId, String targetStepId, String sourcePort) async {
  final targetBlock = _findBlock(_selected!, targetStepId);
  if (targetBlock == null) return;
  
  // Get the target block's input ports from its schema
  final inputSchema = _schemaMap(targetBlock['input_schema'] ?? {});
  final properties = _schemaProps(inputSchema);
  
  if (properties.isEmpty) {
    // No ports to pick, just connect with default
    _pushUndo();
    await _connect(_selected!, sourceStepId, targetStepId, sourcePort: sourcePort);
    setState(() { _wireSourceId = null; _wireSourcePort = null; });
    return;
  }
  
  final portNames = properties.keys.toList();
  
  final pickedPort = await showModalBottomSheet<String>(
    context: context,
    showDragHandle: true,
    builder: (ctx) => Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Connect to which input?', style: Theme.of(ctx).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text('Target: $targetStepId (${targetBlock['block_id'] ?? 'block'})',
              style: Theme.of(ctx).textTheme.bodySmall),
          const SizedBox(height: 12),
          ...portNames.map((port) => ListTile(
                leading: const Icon(Icons.input_rounded, size: 20, color: Color(0xFF6366F1)),
                title: Text(_fieldLabel(port), style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(_schemaHint(properties[port] is Map 
                    ? Map<String, dynamic>.from(properties[port]) 
                    : {})),
                dense: true,
                onTap: () => Navigator.pop(ctx, port),
              )),
        ],
      ),
    ),
  );
  
  if (pickedPort == null) {
    setState(() { _wireSourceId = null; _wireSourcePort = null; });
    return;
  }
  
  _pushUndo();
  await ref.read(ripClientProvider).addGatewayWorkflowWire(
    draftId: _selected!['draft_id'].toString(),
    sourceStepId: sourceStepId,
    targetStepId: targetStepId,
    targetPort: pickedPort,
    sourcePort: sourcePort,
  );
  _refresh(await ref.read(ripClientProvider).gatewayWorkflowCanvas(
      draftId: _selected!['draft_id'].toString()));
  setState(() { _wireSourceId = null; _wireSourcePort = null; });
}
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final workflows = ref.watch(gatewayWorkflowsProvider);
    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF09090F) : const Color(0xFFF4F5F8),
      extendBodyBehindAppBar: true,
      body: workflows.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Workflows unavailable: $e')),
        data: (items) {
          final selected = _selected ?? _initialSelected(items);
          if (selected == null) return _EmptyCanvas(onCreate: _createWorkflow);
          if (!_loadedInitialRun &&
              widget.initialWorkflowId != null &&
              widget.initialRunId != null) {
            _loadedInitialRun = true;
            WidgetsBinding.instance.addPostFrameCallback(
                (_) => _loadRun(selected, widget.initialRunId!));
          }
          return _CanvasShell(
            workflow: selected,
            workflows: items,
            runId: _runId,
            runState: _runState,
            answerController: _answerController,
            runQueryController: _runQueryController,
            undoStack: _undoStack,
            redoStack: _redoStack,
            selectedBlockIds: _selectedBlockIds,
            wireMode: _wireMode,
            wireSourceId: _wireSourceId,
            showGrid: _showGrid,
            showMinimap: _showMinimap,
            snapToGrid: _snapToGrid,
            gridSize: _gridSize,
            onBack: () => Navigator.of(context).maybePop(),
            onSwitch: () => _switchWorkflow(items),
            onCreate: _createWorkflow,
            onAddBlock: () => _addBlock(selected),
            onPublish: () => _publish(selected),
            onRun: () => _runWorkflow(selected),
            onUndo: _undoStack.isEmpty ? null : _undo,
            onRedo: _redoStack.isEmpty ? null : _redo,
            onDeleteStep: (id) {
              _pushUndo();
              _deleteStep(selected, id);
            },
            onUpdateBlockConfig: (id, config) {
              _pushUndo();
              _patchBlockConfig(selected, id, config);
            },
            onMoveBlock: (id, pos) {
              _pushUndo();
              _moveBlock(selected, id, pos);
            },
            onConnect: (src, tgt) {
              _pushUndo();
              _connect(selected, src, tgt);
            },
            onDeleteWire: (id) {
              _pushUndo();
              _deleteWire(selected, id);
            },
            onAnswer: () => _answerMissing(selected),
            onApprove: () => _approve(selected),
            onReject: () => _reject(selected),
            onToggleGrid: () => setState(() => _showGrid = !_showGrid),
            onToggleMinimap: () => setState(() => _showMinimap = !_showMinimap),
            onToggleSnap: () => setState(() => _snapToGrid = !_snapToGrid),
            onToggleWireMode: () {
              setState(() {
                _wireMode = !_wireMode;
                _wireSourceId = null;
                if (_wireMode) _selectedBlockIds.clear();
              });
            },
            onAutoLayout: () {
              _pushUndo();
              _autoLayout(selected);
            },
            onSelectAll: () => setState(() => _selectedBlockIds.addAll(
                _blocks(selected).map((b) => b['step_id']?.toString() ?? ''))),
            onClearSelection: () => setState(() => _selectedBlockIds.clear()),
            onDeleteSelected: () {
              _pushUndo();
              for (final id in _selectedBlockIds.toList())
                _deleteStep(selected, id);
              _selectedBlockIds.clear();
            },
            onCopySelected: () => _copySelected(selected),
            onPaste: () => _paste(selected),
            onDuplicateWorkflow: () => _duplicateWorkflow(selected),
            onExport: () => _exportWorkflow(selected),
            onImport: () => _importWorkflow(),
            onBulkMove: (dx, dy) {
              for (final id in _selectedBlockIds) {
                final b = _findBlock(selected, id);
                if (b != null)
                  _moveBlock(selected, id, _pos(b) + Offset(dx, dy));
              }
            },
            onBlockTap: _handleBlockTap,
          );
        },
      ),
    );
  }

  Map<String, dynamic>? _findBlock(Map<String, dynamic> w, String stepId) {
    for (final b in _blocks(w)) {
      if (b['step_id']?.toString() == stepId) return b;
    }
    return null;
  }

  void _copySelected(Map<String, dynamic> w) {
    _clipboard = [];
    for (final id in _selectedBlockIds) {
      final b = _findBlock(w, id);
      if (b != null) _clipboard!.add(Map<String, dynamic>.from(b));
    }
  }

  Future<void> _paste(Map<String, dynamic> w) async {
    if (_clipboard == null || _clipboard!.isEmpty) return;
    _pushUndo();
    for (final b in _clipboard!) {
      final pos = _pos(b);
      await ref.read(ripClientProvider).appendGatewayWorkflowBlock(
          draftId: w['draft_id'].toString(),
          blockId: b['block_id']?.toString() ?? '',
          config: b['config'] ?? {},
          inputBindings: b['input_bindings'] ?? {},
          position: {'x': pos.dx + 50, 'y': pos.dy + 50});
    }
    _refresh(await ref
        .read(ripClientProvider)
        .gatewayWorkflowCanvas(draftId: w['draft_id'].toString()));
  }

  Future<void> _duplicateWorkflow(Map<String, dynamic> w) async {
    final pid = ref.read(activeProjectIdProvider);
    final created = await ref.read(ripClientProvider).createGatewayWorkflow(
        name: '${w['name'] ?? 'Workflow'} (copy)', projectId: pid);
    ref.invalidate(gatewayWorkflowsProvider);
    for (final b in _blocks(w)) {
      await ref.read(ripClientProvider).appendGatewayWorkflowBlock(
          draftId: created['draft_id'].toString(),
          blockId: b['block_id']?.toString() ?? '',
          config: b['config'] ?? {},
          inputBindings: b['input_bindings'] ?? {},
          position: b['position'] ?? _nextPos(created));
    }
    setState(() => _selected = created);
  }

  void _exportWorkflow(Map<String, dynamic> w) {
    Clipboard.setData(ClipboardData(text: jsonEncode(w)));
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Workflow copied to clipboard')));
  }

  Future<void> _importWorkflow() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text == null) return;
    try {
      final imported = jsonDecode(data!.text!) as Map<String, dynamic>;
      final pid = ref.read(activeProjectIdProvider);
      final created = await ref.read(ripClientProvider).createGatewayWorkflow(
          name: '${imported['name'] ?? 'Imported'}', projectId: pid);
      for (final b in (imported['blocks'] as List?) ?? []) {
        await ref.read(ripClientProvider).appendGatewayWorkflowBlock(
            draftId: created['draft_id'].toString(),
            blockId: b['block_id']?.toString() ?? '',
            config: b['config'] ?? {},
            inputBindings: b['input_bindings'] ?? {},
            position: b['position'] ?? _nextPos(created));
      }
      ref.invalidate(gatewayWorkflowsProvider);
      setState(() => _selected = created);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Invalid workflow JSON: $e')));
    }
  }

  void _autoLayout(Map<String, dynamic> w) {
    final blocks = _blocks(w);
    if (blocks.isEmpty) return;
    double x = 160, y = 220;
    for (final b in blocks) {
      b['position'] = {'x': x, 'y': y};
      x += 280;
      if (x > 16000) {
        x = 160;
        y += 200;
      }
    }
    _refresh(w);
  }

  Future<void> _loadRun(Map<String, dynamic> w, String runId) async {
    final wid = (w['draft_id'] ?? w['workflow_id'])?.toString();
    if (wid == null || !mounted) return;
    final canvas =
        await ref.read(ripClientProvider).gatewayWorkflowCanvas(draftId: wid);
    final state = await ref
        .read(ripClientProvider)
        .gatewayWorkflowRunState(draftId: wid, runId: runId);
    if (!mounted) return;
    setState(() {
      _selected = canvas;
      _runId = runId;
      _runState = state;
    });
    _startPolling(wid, runId);
  }

  Future<void> _switchWorkflow(List<dynamic> items) async {
    final picked = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        showDragHandle: true,
        builder: (_) => _WorkflowPicker(
            items: items, selectedId: _selected?['draft_id']?.toString()));
    if (picked == null) return;
    _poller?.cancel();
    _undoStack.clear();
    _redoStack.clear();
    _selectedBlockIds.clear();
    setState(() {
      _selected = picked;
      _runId = null;
      _runState = null;
    });
  }

  Future<void> _createWorkflow() async {
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => const _NewWorkflowDialog(),
    );
    if (name == null || name.trim().isEmpty) return;
    final pid = ref.read(activeProjectIdProvider);
    final created = await ref
        .read(ripClientProvider)
        .createGatewayWorkflow(name: name.trim(), projectId: pid);
    ref.invalidate(gatewayWorkflowsProvider);
    setState(() => _selected = created);
  }

  Future<void> _addBlock(Map<String, dynamic> w) async {
    final palette = await ref.read(ripClientProvider).gatewayWorkflowPalette();
    if (!mounted) return;
    final blocks = ((palette['blocks'] as List?) ?? [])
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
    final picked = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        isScrollControlled: true,
        backgroundColor: Colors.transparent,
        builder: (_) => _BlockPalette(blocks: blocks));
    if (picked == null || !mounted) return;
    final configured =
        await _QuickConfigSheet.show(context, picked, _blocks(w), ref);
    if (configured == null) return;
    _pushUndo();
    final updated = await ref
        .read(ripClientProvider)
        .appendGatewayWorkflowBlock(
            draftId: w['draft_id'].toString(),
            blockId: picked['id'].toString(),
            config: configured.config,
            inputBindings: configured.bindings,
            position: _nextPos(w));
    _refresh(updated);
  }

  Future<void> _publish(Map<String, dynamic> w) async {
    final u = await ref
        .read(ripClientProvider)
        .publishGatewayWorkflow(w['draft_id'].toString());
    _refresh({...w, 'status': u['status']});
  }

  Future<void> _runWorkflow(Map<String, dynamic> w) async {
    final wid = (w['draft_id'] ?? w['workflow_id'])?.toString();
    if (wid == null) return;
    final query = await showDialog<String>(
      context: context,
      builder: (ctx) => _RunWorkflowDialog(initialQuery: _runQueryController.text),
    );
    if (query == null || query.trim().isEmpty || !mounted) return;
    _runQueryController.text = query.trim();
    try {
      final result = await ref
          .read(ripClientProvider)
          .runGatewayWorkflow(draftId: wid, query: query.trim());
      final runId = result['run_id']?.toString();
      if (runId != null && mounted) {
        setState(() {
          _runId = runId;
          _runState = result;
        });
        _startPolling(wid, runId);
      }
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Run failed: $e')));
    }
  }

void _startPolling(String wid, String rid) {
  _poller?.cancel();
  _poller = Timer.periodic(const Duration(seconds: 2), (_) async {
    try {
      final s = await ref.read(ripClientProvider).gatewayWorkflowRunState(draftId: wid, runId: rid);
      if (!mounted) return;
      setState(() => _runState = s);
      
      // STOP if overall status is completed or failed
      if (s['status'] == 'completed' || s['status'] == 'failed' || s['final_output'] != null) {
        _poller?.cancel();
      }
    } catch (_) {
      _poller?.cancel();
    }
  });
}

  Future<void> _deleteStep(Map<String, dynamic> w, String id) async {
    _refresh(await ref.read(ripClientProvider).deleteGatewayWorkflowBlock(
        draftId: w['draft_id'].toString(), stepId: id));
  }

  Future<void> _patchBlockConfig(Map<String, dynamic> w, String id, Map<String, dynamic> config) async {
    _refresh(await ref.read(ripClientProvider).patchGatewayWorkflowBlock(
        draftId: w['draft_id'].toString(), stepId: id, config: config));
  }

  Future<void> _moveBlock(Map<String, dynamic> w, String id, Offset pos) async {
    _refresh(await ref.read(ripClientProvider).patchGatewayWorkflowBlock(
        draftId: w['draft_id'].toString(),
        stepId: id,
        position: {'x': pos.dx, 'y': pos.dy}));
  }

  Future<void> _connect(Map<String, dynamic> w, String src, String tgt, {String sourcePort = 'output', String targetPort = 'query'}) async {
    await ref.read(ripClientProvider).addGatewayWorkflowWire(
        draftId: w['draft_id'].toString(),
        sourceStepId: src,
        sourcePort: sourcePort,
        targetStepId: tgt,
        targetPort: targetPort);
    _refresh(await ref
        .read(ripClientProvider)
        .gatewayWorkflowCanvas(draftId: w['draft_id'].toString()));
  }

  Future<void> _deleteWire(Map<String, dynamic> w, String id) async {
    final r = await ref.read(ripClientProvider).deleteGatewayWorkflowWire(
        draftId: w['draft_id'].toString(), wireId: id);
    _refresh({...w, 'wires': r['wires'] ?? []});
  }

  Future<void> _answerMissing(Map<String, dynamic> w) async {
    final missing = _missingStep(_runState);
    if (missing == null ||
        _runId == null ||
        _answerController.text.trim().isEmpty) return;
    final s = await ref.read(ripClientProvider).answerGatewayWorkflowInput(
        draftId: w['draft_id'].toString(),
        runId: _runId!,
        stepId: missing,
        value: _answerController.text.trim());
    setState(() => _runState = s);
    _answerController.clear();
    _startPolling(w['draft_id'].toString(), _runId!);
  }

  Future<void> _approve(Map<String, dynamic> w) async {
    if (_runId == null) return;
    final r = await ref.read(ripClientProvider).approveGatewayWorkflowRun(
        draftId: w['draft_id'].toString(), runId: _runId!);
    setState(
        () => _runState = Map<String, dynamic>.from(r['state'] as Map? ?? {}));
    _startPolling(w['draft_id'].toString(), _runId!);
  }

  Future<void> _reject(Map<String, dynamic> w) async {
    if (_runId == null) return;
    final r = await ref.read(ripClientProvider).rejectGatewayWorkflowRun(
        draftId: w['draft_id'].toString(), runId: _runId!);
    setState(
        () => _runState = Map<String, dynamic>.from(r['state'] as Map? ?? {}));
  }

  void _refresh(Map<String, dynamic> u) {
    ref.invalidate(gatewayWorkflowsProvider);
    if (mounted)
      setState(() {
        _selected = {...?_selected, ...u};
      });
  }
}

// ============================================================
// CANVAS SHELL
// ============================================================
class _CanvasShell extends StatelessWidget {
  const _CanvasShell(
      {required this.workflow,
      required this.workflows,
      required this.runId,
      required this.runState,
      required this.answerController,
      required this.runQueryController,
      required this.undoStack,
      required this.redoStack,
      required this.selectedBlockIds,
      required this.wireMode,
      required this.wireSourceId,
      required this.showGrid,
      required this.showMinimap,
      required this.snapToGrid,
      required this.gridSize,
      required this.onBack,
      required this.onSwitch,
      required this.onCreate,
      required this.onAddBlock,
      required this.onPublish,
      required this.onRun,
      required this.onUndo,
      required this.onRedo,
      required this.onDeleteStep,
      required this.onUpdateBlockConfig,
      required this.onMoveBlock,
      required this.onConnect,
      required this.onDeleteWire,
      required this.onAnswer,
      required this.onApprove,
      required this.onReject,
      required this.onToggleGrid,
      required this.onToggleMinimap,
      required this.onToggleSnap,
      required this.onToggleWireMode,
      required this.onAutoLayout,
      required this.onSelectAll,
      required this.onClearSelection,
      required this.onDeleteSelected,
      required this.onCopySelected,
      required this.onPaste,
      required this.onDuplicateWorkflow,
      required this.onExport,
      required this.onImport,
      required this.onBulkMove,
      required this.onBlockTap,
      required this.paletteBlocks});
  final Map<String, dynamic> workflow;
  final List<dynamic> workflows;
  final List<dynamic> paletteBlocks;
  final String? runId;
  final Map<String, dynamic>? runState;
  final TextEditingController answerController, runQueryController;
  final List<Map<String, dynamic>> undoStack, redoStack;
  final Set<String> selectedBlockIds;
  final bool wireMode, showGrid, showMinimap, snapToGrid;
  final double gridSize;
  final String? wireSourceId;
  final VoidCallback onBack,
      onSwitch,
      onCreate,
      onAddBlock,
      onPublish,
      onRun,
      onAnswer,
      onApprove,
      onReject,
      onToggleGrid,
      onToggleMinimap,
      onToggleSnap,
      onToggleWireMode,
      onAutoLayout,
      onSelectAll,
      onClearSelection,
      onDeleteSelected,
      onCopySelected,
      onPaste,
      onDuplicateWorkflow,
      onExport,
      onImport;
  final VoidCallback? onUndo, onRedo;
  final ValueChanged<String> onDeleteStep, onDeleteWire;
  final void Function(String, Map<String, dynamic>) onUpdateBlockConfig;
  final void Function(String, Offset) onMoveBlock;
  final void Function(String, String) onConnect;
  final void Function(double, double) onBulkMove;
  final void Function(String, {bool isOutputTap, String? outputPort}) onBlockTap;

  @override
  Widget build(BuildContext context) {
    final blocks = _blocks(workflow),
        wires = _wires(workflow),
        state = runState;
    final top = MediaQuery.paddingOf(context).top,
        bottom = MediaQuery.paddingOf(context).bottom;
    final isRunning = state != null && runId != null;
    return Stack(children: [
      Positioned.fill(
          child: _Canvas(
              blocks: blocks,
              wires: wires,
              runState: state,
              selectedBlockIds: selectedBlockIds,
              wireMode: wireMode,
              wireSourceId: wireSourceId,
              showGrid: showGrid,
              snapToGrid: snapToGrid,
              gridSize: gridSize,
              onMoveBlock: onMoveBlock,
              onConnect: onConnect,
              onDeleteBlock: onDeleteStep,
              onDeleteWire: onDeleteWire,
              onBlockTap: onBlockTap,
              onBulkMove: onBulkMove,
              onUpdateBlockConfig: onUpdateBlockConfig,
              paletteBlocks: paletteBlocks)),
      Positioned(
          top: top + 10,
          left: 12,
          right: 12,
          child: _Header(
              title: '${workflow['name'] ?? 'Workflow'}',
              status: '${workflow['status'] ?? 'draft'}',
              blockCount: blocks.length,
              wireCount: wires.length,
              isRunning: isRunning,
              selectedCount: selectedBlockIds.length,
              canUndo: undoStack.isNotEmpty,
              canRedo: redoStack.isNotEmpty,
              onBack: onBack,
              onSwitch: onSwitch,
              onCreate: onCreate,
              onUndo: onUndo,
              onRedo: onRedo,
              onToggleGrid: onToggleGrid,
              onToggleMinimap: onToggleMinimap,
              onToggleSnap: onToggleSnap,
              onToggleWireMode: onToggleWireMode,
              onAutoLayout: onAutoLayout,
              showGrid: showGrid,
              showMinimap: showMinimap,
              snapToGrid: snapToGrid,
              wireMode: wireMode)),
      if (selectedBlockIds.isNotEmpty)
        Positioned(
            top: top + 70,
            left: 12,
            right: 12,
            child: _SelectionToolbar(
                count: selectedBlockIds.length,
                onClear: onClearSelection,
                onDelete: onDeleteSelected,
                onCopy: onCopySelected,
                onMoveLeft: () => onBulkMove(-gridSize, 0),
                onMoveRight: () => onBulkMove(gridSize, 0),
                onMoveUp: () => onBulkMove(0, -gridSize),
                onMoveDown: () => onBulkMove(0, gridSize))),
      Positioned(
          right: 14,
          bottom: bottom + (isRunning ? 140 : 18),
          child: _Dock(
              hasBlocks: blocks.isNotEmpty,
              onAddBlock: onAddBlock,
              onPublish: onPublish,
              onRun: onRun,
              onPaste: onPaste,
              onDuplicate: onDuplicateWorkflow,
              onExport: onExport,
              onImport: onImport)),
      if (isRunning && state != null)
        Positioned(
            left: 12,
            right: 12,
            bottom: bottom + 14,
            child: _RunPanel(
                runId: runId,
                state: state,
                answerController: answerController,
                onAnswer: onAnswer,
                onApprove: onApprove,
                onReject: onReject)),
      if (showMinimap && blocks.isNotEmpty)
        Positioned(
            left: 8,
            bottom: bottom + 100,
            child: _Minimap(blocks: blocks, wires: wires)),
      // Wire mode instruction banner
      if (wireMode)
        Positioned(
          top: top + 10,
          right: 12,
          child: Material(
            color: wireSourceId != null 
                ? Colors.green.withValues(alpha: 0.9)
                : Colors.orange.withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    wireSourceId != null ? Icons.arrow_forward_rounded : Icons.touch_app_rounded,
                    size: 16,
                    color: Colors.white,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    wireSourceId != null ? 'Now tap IN on target block' : 'Tap OUT on source block',
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ],
              ),
            ),
          ),
        ),
    ]);
  }
}

// ============================================================
// HEADER
// ============================================================
class _Header extends StatelessWidget {
  const _Header(
      {required this.title,
      required this.status,
      required this.blockCount,
      required this.wireCount,
      required this.isRunning,
      required this.selectedCount,
      required this.canUndo,
      required this.canRedo,
      required this.onBack,
      required this.onSwitch,
      required this.onCreate,
      required this.onUndo,
      required this.onRedo,
      required this.onToggleGrid,
      required this.onToggleMinimap,
      required this.onToggleSnap,
      required this.onToggleWireMode,
      required this.onAutoLayout,
      required this.showGrid,
      required this.showMinimap,
      required this.snapToGrid,
      required this.wireMode});
  final String title, status;
  final int blockCount, wireCount, selectedCount;
  final bool isRunning, canUndo, canRedo;
  final VoidCallback onBack,
      onSwitch,
      onCreate,
      onToggleGrid,
      onToggleMinimap,
      onToggleSnap,
      onToggleWireMode,
      onAutoLayout;
  final VoidCallback? onUndo, onRedo;
  final bool showGrid, showMinimap, snapToGrid, wireMode;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
              width: 1,
            ),
          ),
          child: Row(
            children: [
              IconButton(
                tooltip: 'Open Navigation',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  Scaffold.of(context).openDrawer();
                },
                icon: Icon(Icons.menu_rounded, color: isDark ? Colors.white : Colors.black87),
                visualDensity: VisualDensity.compact,
              ),
              Expanded(
                child: InkWell(
                  borderRadius: BorderRadius.circular(12),
                  onTap: () {
                    HapticFeedback.selectionClick();
                    onSwitch();
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: isDark ? Colors.white : Colors.black87,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                            const SizedBox(width: 4),
                            Icon(Icons.unfold_more_rounded, size: 14, color: isDark ? Colors.white54 : Colors.black45),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            Text(
                              '$status • $blockCount blocks • $wireCount wires',
                              style: TextStyle(
                                color: isDark ? Colors.white54 : Colors.black54,
                                fontSize: 11,
                              ),
                            ),
                            if (isRunning) ...[
                              const SizedBox(width: 6),
                              Container(
                                width: 6,
                                height: 6,
                                decoration: const BoxDecoration(
                                  color: Color(0xFF10B981),
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 3),
                              const Text(
                                'Live',
                                style: TextStyle(color: Color(0xFF10B981), fontSize: 10, fontWeight: FontWeight.bold),
                              ),
                            ],
                            if (selectedCount > 0) ...[
                              const SizedBox(width: 6),
                              Text(
                                '$selectedCount selected',
                                style: const TextStyle(color: Color(0xFF6366F1), fontSize: 10, fontWeight: FontWeight.bold),
                              ),
                            ],
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              IconButton(
                tooltip: 'Undo',
                onPressed: onUndo != null
                    ? () {
                        HapticFeedback.selectionClick();
                        onUndo!();
                      }
                    : null,
                icon: Icon(Icons.undo_rounded, size: 18, color: onUndo != null ? (isDark ? Colors.white70 : Colors.black87) : (isDark ? Colors.white24 : Colors.black26)),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Redo',
                onPressed: onRedo != null
                    ? () {
                        HapticFeedback.selectionClick();
                        onRedo!();
                      }
                    : null,
                icon: Icon(Icons.redo_rounded, size: 18, color: onRedo != null ? (isDark ? Colors.white70 : Colors.black87) : (isDark ? Colors.white24 : Colors.black26)),
                visualDensity: VisualDensity.compact,
              ),
              PopupMenuButton<String>(
                tooltip: 'Canvas Settings',
                icon: Icon(Icons.more_vert_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(
                    color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.1),
                  ),
                ),
                color: isDark ? const Color(0xFF13132B).withValues(alpha: 0.96) : Colors.white.withValues(alpha: 0.96),
                elevation: 8,
                onSelected: (v) {
                  HapticFeedback.selectionClick();
                  switch (v) {
                    case 'grid':
                      onToggleGrid();
                    case 'snap':
                      onToggleSnap();
                    case 'minimap':
                      onToggleMinimap();
                    case 'wire':
                      onToggleWireMode();
                    case 'layout':
                      onAutoLayout();
                  }
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'grid',
                    child: Row(
                      children: [
                        Icon(showGrid ? Icons.check_box_rounded : Icons.check_box_outline_blank_rounded, size: 18, color: showGrid ? const Color(0xFF6366F1) : null),
                        const SizedBox(width: 8),
                        const Text('Show Grid'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'snap',
                    child: Row(
                      children: [
                        Icon(snapToGrid ? Icons.check_box_rounded : Icons.check_box_outline_blank_rounded, size: 18, color: snapToGrid ? const Color(0xFF6366F1) : null),
                        const SizedBox(width: 8),
                        const Text('Snap to Grid'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'minimap',
                    child: Row(
                      children: [
                        Icon(showMinimap ? Icons.check_box_rounded : Icons.check_box_outline_blank_rounded, size: 18, color: showMinimap ? const Color(0xFF6366F1) : null),
                        const SizedBox(width: 8),
                        const Text('Minimap'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'wire',
                    child: Row(
                      children: [
                        Icon(wireMode ? Icons.check_box_rounded : Icons.check_box_outline_blank_rounded, size: 18, color: wireMode ? const Color(0xFF6366F1) : null),
                        const SizedBox(width: 8),
                        const Text('Wire Mode'),
                      ],
                    ),
                  ),
                  const PopupMenuDivider(),
                  const PopupMenuItem(
                    value: 'layout',
                    child: Row(
                      children: [
                        Icon(Icons.auto_fix_high_rounded, size: 18),
                        SizedBox(width: 8),
                        Text('Auto Layout'),
                      ],
                    ),
                  ),
                ],
              ),
              IconButton(
                tooltip: 'New Workflow',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onCreate();
                },
                icon: const Icon(Icons.add_rounded, size: 20, color: Color(0xFF6366F1)),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================
// SELECTION TOOLBAR
// ============================================================
class _SelectionToolbar extends StatelessWidget {
  const _SelectionToolbar(
      {required this.count,
      required this.onClear,
      required this.onDelete,
      required this.onCopy,
      required this.onMoveLeft,
      required this.onMoveRight,
      required this.onMoveUp,
      required this.onMoveDown});
  final int count;
  final VoidCallback onClear,
      onDelete,
      onCopy,
      onMoveLeft,
      onMoveRight,
      onMoveUp,
      onMoveDown;
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '$count selected',
                style: TextStyle(
                  color: isDark ? Colors.white70 : Colors.black87,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                tooltip: 'Move left',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onMoveLeft();
                },
                icon: const Icon(Icons.arrow_left_rounded, size: 20),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Move right',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onMoveRight();
                },
                icon: const Icon(Icons.arrow_right_rounded, size: 20),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Move up',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onMoveUp();
                },
                icon: const Icon(Icons.arrow_upward_rounded, size: 20),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Move down',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onMoveDown();
                },
                icon: const Icon(Icons.arrow_downward_rounded, size: 20),
                visualDensity: VisualDensity.compact,
              ),
              const SizedBox(width: 4),
              IconButton(
                tooltip: 'Copy',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onCopy();
                },
                icon: const Icon(Icons.copy_rounded, size: 18),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Delete',
                onPressed: () {
                  HapticFeedback.mediumImpact();
                  onDelete();
                },
                icon: const Icon(Icons.delete_outline_rounded, size: 18, color: Colors.redAccent),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Clear',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onClear();
                },
                icon: const Icon(Icons.close_rounded, size: 18),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================
// DOCK
// ============================================================
class _Dock extends StatelessWidget {
  const _Dock(
      {required this.hasBlocks,
      required this.onAddBlock,
      required this.onPublish,
      required this.onRun,
      required this.onPaste,
      required this.onDuplicate,
      required this.onExport,
      required this.onImport});
  final bool hasBlocks;
  final VoidCallback onAddBlock,
      onPublish,
      onRun,
      onPaste,
      onDuplicate,
      onExport,
      onImport;
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(30),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(30),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                tooltip: 'Run Workflow',
                onPressed: hasBlocks
                    ? () {
                        HapticFeedback.mediumImpact();
                        onRun();
                      }
                    : null,
                icon: Icon(
                  Icons.play_arrow_rounded,
                  color: hasBlocks ? const Color(0xFF10B981) : (isDark ? Colors.white24 : Colors.black26),
                ),
              ),
              const SizedBox(height: 4),
              IconButton(
                tooltip: 'Publish Workflow',
                onPressed: hasBlocks
                    ? () {
                        HapticFeedback.selectionClick();
                        onPublish();
                      }
                    : null,
                icon: Icon(
                  Icons.publish_rounded,
                  color: hasBlocks ? (isDark ? Colors.white70 : Colors.black87) : (isDark ? Colors.white24 : Colors.black26),
                ),
              ),
              const SizedBox(height: 4),
              Container(
                decoration: const BoxDecoration(
                  color: Color(0xFF6366F1),
                  shape: BoxShape.circle,
                ),
                child: IconButton(
                  tooltip: 'Add Block',
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    onAddBlock();
                  },
                  icon: const Icon(Icons.add_rounded, color: Colors.white),
                ),
              ),
              const SizedBox(height: 4),
              PopupMenuButton<String>(
                tooltip: 'More Actions',
                icon: Icon(Icons.more_horiz_rounded, color: isDark ? Colors.white70 : Colors.black87),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(
                    color: isDark ? Colors.white.withValues(alpha: 0.15) : Colors.black.withValues(alpha: 0.1),
                  ),
                ),
                color: isDark ? const Color(0xFF13132B).withValues(alpha: 0.96) : Colors.white.withValues(alpha: 0.96),
                elevation: 8,
                onSelected: (v) {
                  HapticFeedback.selectionClick();
                  switch (v) {
                    case 'paste':
                      onPaste();
                    case 'duplicate':
                      onDuplicate();
                    case 'export':
                      onExport();
                    case 'import':
                      onImport();
                  }
                },
                itemBuilder: (_) => [
                  PopupMenuItem(
                    value: 'paste',
                    child: Row(
                      children: [
                        Icon(Icons.paste_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        const SizedBox(width: 8),
                        const Text('Paste Block'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'duplicate',
                    child: Row(
                      children: [
                        Icon(Icons.copy_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        const SizedBox(width: 8),
                        const Text('Duplicate Workflow'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'export',
                    child: Row(
                      children: [
                        Icon(Icons.upload_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        const SizedBox(width: 8),
                        const Text('Export JSON'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'import',
                    child: Row(
                      children: [
                        Icon(Icons.download_rounded, size: 18, color: isDark ? Colors.white70 : Colors.black87),
                        const SizedBox(width: 8),
                        const Text('Import JSON'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================
// MINIMAP
// ============================================================
class _Minimap extends StatelessWidget {
  const _Minimap({required this.blocks, required this.wires});
  final List<Map<String, dynamic>> blocks, wires;
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          width: 140,
          height: 100,
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
            ),
          ),
          child: CustomPaint(
            size: const Size(128, 88),
            painter: _MinimapPainter(
              blocks: blocks,
              wires: wires,
              cs: Theme.of(context).colorScheme,
            ),
          ),
        ),
      ),
    );
  }
}

class _MinimapPainter extends CustomPainter {
  const _MinimapPainter(
      {required this.blocks, required this.wires, required this.cs});
  final List<Map<String, dynamic>> blocks, wires;
  final ColorScheme cs;
  @override
  void paint(Canvas c, Size s) {
    final sx = s.width / 18000, sy = s.height / 12000;
    final bp = Paint()..color = cs.primary.withValues(alpha: 0.5);
    for (final b in blocks) {
      final p = _pos(b);
      c.drawRect(Rect.fromLTWH(p.dx * sx, p.dy * sy, 230 * sx, 150 * sy), bp);
    }
    final wp = Paint()
      ..color = cs.outline.withValues(alpha: 0.4)
      ..strokeWidth = 0.5;
    final map = {for (final b in blocks) b['step_id']?.toString(): b};
    for (final w in wires) {
      final src = map[w['source_step_id']?.toString()],
          tgt = map[w['target_step_id']?.toString()];
      if (src == null || tgt == null) continue;
      final a = _pos(src), b = _pos(tgt);
      c.drawLine(Offset(a.dx * sx + 115 * sx, a.dy * sy + 75 * sy),
          Offset(b.dx * sx + 115 * sx, b.dy * sy + 75 * sy), wp);
    }
  }

  @override
  bool shouldRepaint(covariant _MinimapPainter o) =>
      o.blocks != blocks || o.wires != wires;
}

// ============================================================
// RUN PANEL
// ============================================================
class _RunPanel extends StatelessWidget {
  const _RunPanel(
      {required this.runId,
      required this.state,
      required this.answerController,
      required this.onAnswer,
      required this.onApprove,
      required this.onReject});
  final String? runId;
  final Map<String, dynamic> state;
  final TextEditingController answerController;
  final VoidCallback onAnswer, onApprove, onReject;
  @override
  Widget build(BuildContext context) => Material(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.94),
      elevation: 12,
      borderRadius: BorderRadius.circular(16),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.4,
        ),
        child: SingleChildScrollView(
          child: Padding(
              padding: const EdgeInsets.all(12),
              child: _RunState(
                  runId: runId,
                  state: state,
                  answerController: answerController,
                  onAnswer: onAnswer,
                  onApprove: onApprove,
                  onReject: onReject)),
        ),
      ));
}

class _RunState extends StatelessWidget {
  const _RunState(
      {required this.runId,
      required this.state,
      required this.answerController,
      required this.onAnswer,
      required this.onApprove,
      required this.onReject});
  final String? runId;
  final Map<String, dynamic> state;
  final TextEditingController answerController;
  final VoidCallback onAnswer, onApprove, onReject;
  @override
  Widget build(BuildContext context) {
    final trace = _makeTrace(runId ?? '', state);
    final awaiting = _hasStatus(state, 'awaiting_approval');
    final missing = _missingStep(state);
    final done = state['final_output'] != null ||
        _hasStatus(state, 'failed') ||
        _hasStatus(state, 'completed');
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          done
              ? PipelineSummaryChip(trace: trace)
              : PipelineStepList(trace: trace),
          if (state['error'] != null &&
              state['error'].toString().isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(8)),
                child: Text('${state['error']}',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.onErrorContainer)))
          ],
          if (missing != null) ...[
            const SizedBox(height: 8),
            TextField(
                controller: answerController,
                decoration: InputDecoration(
                    labelText: 'Missing input',
                    suffixIcon: IconButton(
                        tooltip: 'Submit',
                        icon: const Icon(Icons.send_rounded),
                        onPressed: onAnswer)),
                onSubmitted: (_) => onAnswer())
          ],
          if (awaiting) ...[
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                  child: FilledButton.icon(
                      onPressed: onApprove,
                      icon: const Icon(Icons.check_rounded),
                      label: const Text('Approve'))),
              const SizedBox(width: 8),
              Expanded(
                  child: OutlinedButton.icon(
                      onPressed: onReject,
                      icon: const Icon(Icons.close_rounded),
                      label: const Text('Reject')))
            ])
          ],
          if (state['final_output'] != null) ...[
            const SizedBox(height: 8),
            Container(
              constraints: const BoxConstraints(maxHeight: 200),
              child: SingleChildScrollView(
                child: SelectableText('${state['final_output']}',
                    style: Theme.of(context).textTheme.bodySmall),
              ),
            ),
          ],
        ]);
  }
}

// ============================================================
// CANVAS
// ============================================================
class _Canvas extends StatefulWidget {
  const _Canvas(
      {required this.blocks,
      required this.wires,
      required this.runState,
      required this.selectedBlockIds,
      required this.wireMode,
      required this.wireSourceId,
      required this.showGrid,
      required this.snapToGrid,
      required this.gridSize,
      required this.onMoveBlock,
      required this.onConnect,
      required this.onDeleteBlock,
      required this.onDeleteWire,
      required this.onBlockTap,
      required this.onBulkMove,
      required this.onUpdateBlockConfig,
      required this.paletteBlocks});
  final List<Map<String, dynamic>> blocks, wires;
  final List<dynamic> paletteBlocks;
  final Map<String, dynamic>? runState;
  final Set<String> selectedBlockIds;
  final bool wireMode, showGrid, snapToGrid;
  final double gridSize;
  final String? wireSourceId;
  final void Function(String, Offset) onMoveBlock;
  final void Function(String, String) onConnect;
  final void Function(String, Map<String, dynamic>) onUpdateBlockConfig;
  final ValueChanged<String> onDeleteBlock, onDeleteWire;
  final void Function(String, {bool isOutputTap, String? outputPort}) onBlockTap;
  final void Function(double, double) onBulkMove;
  @override
  State<_Canvas> createState() => _CanvasState();
}

class _CanvasState extends State<_Canvas> {
  static const _cw = 18000.0, _ch = 12000.0, _bw = 230.0, _bh = 150.0;
  String? _selWire;
  Offset? _lassoStart, _lassoEnd;

  Offset _snap(Offset p) => widget.snapToGrid
      ? Offset((p.dx / widget.gridSize).round() * widget.gridSize,
          (p.dy / widget.gridSize).round() * widget.gridSize)
      : p;

  void _hitWire(Offset p) {
    final map = {for (final b in widget.blocks) b['step_id']?.toString(): b};
    for (final w in widget.wires.reversed) {
      final s = map[w['source_step_id']?.toString()],
          t = map[w['target_step_id']?.toString()];
      if (s == null || t == null) continue;
      if (_nearWire(
          p, _pos(s) + Offset(_bw, 108), _pos(t) + const Offset(0, 108))) {
        setState(() {
          _selWire = w['id']?.toString();
        });
        _showWireDetails(w);
        return;
      }
    }
    setState(() => _selWire = null);
  }

  bool _nearWire(Offset p, Offset a, Offset b) {
    for (var i = 0; i <= 16; i++) {
      final t = i / 16;
      if ((Offset(_cub(a.dx, a.dx + 110, b.dx - 110, b.dx, t),
                      _cub(a.dy, a.dy, b.dy, b.dy, t)) -
                  p)
              .distance <=
          28) return true;
    }
    return false;
  }

  double _cub(double a, double b, double c, double d, double t) {
    final mt = 1 - t;
    return mt * mt * mt * a +
        3 * mt * mt * t * b +
        3 * mt * t * t * c +
        t * t * t * d;
  }

  void _showWireDetails(Map<String, dynamic> w) {
    showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (_) => Padding(
            padding: const EdgeInsets.all(16),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(
                  'Wire: ${w['source_step_id'] ?? '?'} \u2192 ${w['target_step_id'] ?? '?'}',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              if (w['label'] != null) Text('Label: ${w['label']}'),
              Text('Port: ${w['target_port'] ?? 'default'}'),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                    child: OutlinedButton.icon(
                        onPressed: () {
                          Navigator.pop(context);
                          widget.onDeleteWire(w['id']?.toString() ?? '');
                        },
                        icon: const Icon(Icons.link_off_rounded),
                        label: const Text('Disconnect'))),
                const SizedBox(width: 8),
                Expanded(
                    child: FilledButton.icon(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.check_rounded),
                        label: const Text('Close')))
              ]),
            ])));
  }

  void _showBlockDetails(Map<String, dynamic> b) {
    showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (_) => _BlockDetails(
            block: b,
            status: _stepStatus(widget.runState, b['step_id']?.toString()),
            output: _stepOutput(widget.runState, b['step_id']?.toString()),
            wires: widget.wires
                .where((w) =>
                    w['source_step_id'] == b['step_id'] ||
                    w['target_step_id'] == b['step_id'])
                .map((w) => Map<String, dynamic>.from(w))
                .toList(),
            onConnect: () {
              Navigator.pop(context);
              widget.onBlockTap(b['step_id']?.toString() ?? '', isOutputTap: true);
            },
            onDelWires: () {
              Navigator.pop(context);
              for (final w in widget.wires) {
                if ((w['source_step_id'] == b['step_id'] ||
                        w['target_step_id'] == b['step_id']) &&
                    w['id'] != null) widget.onDeleteWire(w['id'].toString());
              }
            },
            onDel: () {
              Navigator.pop(context);
              widget.onDeleteBlock(b['step_id']?.toString() ?? '');
            },
            onConfigChanged: (newConfig) {
              final stepId = b['step_id']?.toString() ?? '';
              widget.onUpdateBlockConfig(stepId, newConfig);
              // Optimistically update local block map to avoid full rebuild flashing
              b['config'] = newConfig; 
            },
            onAddNote: (note) {
              b['note'] = note;
              setState(() {});
            }));
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgColor = isDark ? const Color(0xFF09090F) : const Color(0xFFF3F4F8);
    return Container(
      color: bgColor,
      child: Stack(
        children: [
          InteractiveViewer(
            minScale: 0.25,
            maxScale: 3.0,
            boundaryMargin: const EdgeInsets.all(3000),
            constrained: false,
            child: SizedBox(
              width: _cw,
              height: _ch,
              child: Stack(
                children: [
                  if (widget.showGrid)
                    CustomPaint(
                      size: const Size(_cw, _ch),
                      painter: _GridPainter(gridSize: widget.gridSize, isDark: isDark),
                    ),
                  Positioned(
                    left: 80,
                    top: 220,
                    child: _EndPoint(
                      icon: Icons.login_rounded,
                      title: 'TRIGGER',
                      subtitle: 'Chat query',
                      color: const Color(0xFF6366F1),
                    ),
                  ),
                  Positioned(
                    left: _cw - 340,
                    top: 220,
                    child: _EndPoint(
                      icon: Icons.logout_rounded,
                      title: 'RESPONSE',
                      subtitle: 'Output',
                      color: const Color(0xFF22C55E),
                    ),
                  ),
                  GestureDetector(
                    behavior: HitTestBehavior.translucent,
                    onTapDown: (d) => _hitWire(d.localPosition),
                    child: CustomPaint(
                      size: const Size(_cw, _ch),
                      painter: _WirePainter(
                        blocks: widget.blocks,
                        wires: widget.wires,
                        runState: widget.runState,
                        isDark: isDark,
                        selWire: _selWire,
                      ),
                    ),
                  ),
                  ...widget.blocks.map((b) {
                    final sid = b['step_id']?.toString() ?? '';
                    final sel = widget.selectedBlockIds.contains(sid);
                    return Positioned(
                      left: _pos(b).dx,
                      top: _pos(b).dy,
                      width: _bw,
                      height: _bh,
                      child: GestureDetector(
                        onDoubleTap: () => _showBlockDetails(b),
                        onPanUpdate: (d) {
                          final p = _snap(_pos(b) + d.delta);
                          b['position'] = {
                            'x': p.dx.clamp(80, _cw - _bw - 240),
                            'y': p.dy.clamp(120, _ch - _bh - 240)
                          };
                          setState(() {});
                        },
                        onPanEnd: (d) => widget.onMoveBlock(sid, _snap(_pos(b))),
                        child: _BlockCard(
                          block: b,
                          status: _stepStatus(widget.runState, sid),
                          selected: sel,
                          paletteBlocks: widget.paletteBlocks,
                          wireSrc: sid == widget.wireSourceId,
                          note: b['note']?.toString(),
                          isWireTarget: widget.wireMode &&
                              widget.wireSourceId != null &&
                              widget.wireSourceId != sid,
                          onTapOutput: (port) => widget.onBlockTap(sid, isOutputTap: true, outputPort: port),
                          onTapInput: () => widget.onBlockTap(sid, isOutputTap: false),
                        ),
                      ),
                    );
                  }),
                  if (_lassoStart != null && _lassoEnd != null)
                    Positioned.fill(
                      child: CustomPaint(
                        painter: _LassoPainter(
                          start: _lassoStart!,
                          end: _lassoEnd!,
                          isDark: isDark,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (_selWire != null)
            Positioned(
              left: 12,
              right: 12,
              bottom: 12,
              child: _WireBar(
                wire: widget.wires.firstWhere(
                  (w) => w['id']?.toString() == _selWire,
                  orElse: () => const {},
                ),
                onDelete: () {
                  widget.onDeleteWire(_selWire!);
                  setState(() => _selWire = null);
                },
                onClear: () => setState(() => _selWire = null),
              ),
            ),
        ],
      ),
    );
  }
}

// ============================================================
// PAINTERS
// ============================================================
class _GridPainter extends CustomPainter {
  const _GridPainter({required this.gridSize, required this.isDark});
  final double gridSize;
  final bool isDark;

  @override
  void paint(Canvas c, Size s) {
    final p = Paint()
      ..color = isDark
          ? Colors.white.withValues(alpha: 0.05)
          : Colors.black.withValues(alpha: 0.04)
      ..strokeWidth = 0.75;
    for (double x = 0; x < s.width; x += gridSize) {
      c.drawLine(Offset(x, 0), Offset(x, s.height), p);
    }
    for (double y = 0; y < s.height; y += gridSize) {
      c.drawLine(Offset(0, y), Offset(s.width, y), p);
    }
  }

  @override
  bool shouldRepaint(covariant _GridPainter o) =>
      o.gridSize != gridSize || o.isDark != isDark;
}

class _LassoPainter extends CustomPainter {
  const _LassoPainter({
    required this.start,
    required this.end,
    required this.isDark,
  });

  final Offset start, end;
  final bool isDark;

  @override
  void paint(Canvas c, Size s) {
    c.drawRect(
      Rect.fromPoints(start, end),
      Paint()
        ..color = const Color(0xFF6366F1).withValues(alpha: 0.15)
        ..style = PaintingStyle.fill,
    );
    c.drawRect(
      Rect.fromPoints(start, end),
      Paint()
        ..color = const Color(0xFF6366F1).withValues(alpha: 0.6)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );
  }

  @override
  bool shouldRepaint(covariant _LassoPainter o) =>
      o.start != start || o.end != end || o.isDark != isDark;
}

class _WirePainter extends CustomPainter {
  const _WirePainter({
    required this.blocks,
    required this.wires,
    required this.runState,
    required this.isDark,
    required this.selWire,
  });

  final List<Map<String, dynamic>> blocks, wires;
  final Map<String, dynamic>? runState;
  final bool isDark;
  final String? selWire;

  @override
  void paint(Canvas c, Size s) {
    final map = {for (final b in blocks) b['step_id']?.toString(): b};
    for (final w in wires) {
      final src = map[w['source_step_id']?.toString()],
          tgt = map[w['target_step_id']?.toString()];
      if (src == null || tgt == null) continue;
      final a = _pos(src) + const Offset(230, 75),
          b = _pos(tgt) + const Offset(0, 75);
      final p = Path()
        ..moveTo(a.dx, a.dy)
        ..cubicTo(a.dx + 90, a.dy, b.dx - 90, b.dy, b.dx, b.dy);
      final st = _stepStatus(runState, w['target_step_id']?.toString()),
          sel = w['id']?.toString() == selWire;

      final wireColor = _statusColor(st, isDark);

      if (sel || st == 'running') {
        c.drawPath(
          p,
          Paint()
            ..color = (sel ? const Color(0xFF6366F1) : wireColor).withValues(alpha: 0.3)
            ..strokeWidth = sel ? 8 : 6
            ..style = PaintingStyle.stroke
            ..strokeCap = StrokeCap.round
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
        );
      }

      c.drawPath(
        p,
        Paint()
          ..color = wireColor.withValues(alpha: isDark ? 0.9 : 0.85)
          ..strokeWidth = sel ? 4.5 : (st == 'running' ? 3.5 : 2.2)
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round,
      );

      final mid = Offset.lerp(a, b, 0.5)!;
      if (st != 'running') {
        c.drawPath(
          Path()
            ..moveTo(mid.dx - 4, mid.dy - 5)
            ..lineTo(mid.dx + 6, mid.dy)
            ..lineTo(mid.dx - 4, mid.dy + 5)
            ..close(),
          Paint()
            ..color = wireColor
            ..style = PaintingStyle.fill,
        );
      }
      if (sel) {
        c.drawCircle(mid, 7, Paint()..color = const Color(0xFF6366F1));
        c.drawCircle(mid, 4, Paint()..color = Colors.white);
      }
      if (w['label'] != null) {
        final tp = TextPainter(
          text: TextSpan(
            text: w['label'],
            style: TextStyle(
              color: isDark ? Colors.white70 : Colors.black87,
              fontSize: 10,
              fontWeight: FontWeight.w500,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        final labelRect = Rect.fromCenter(
          center: mid - Offset(0, tp.height + 4),
          width: tp.width + 12,
          height: tp.height + 4,
        );
        c.drawRRect(
          RRect.fromRectAndRadius(labelRect, const Radius.circular(6)),
          Paint()..color = isDark ? const Color(0xFF181826) : Colors.white,
        );
        tp.paint(
          c,
          mid - Offset(tp.width / 2, tp.height + 6),
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _WirePainter o) =>
      o.blocks != blocks ||
      o.wires != wires ||
      o.runState != runState ||
      o.isDark != isDark ||
      o.selWire != selWire;
}

// ============================================================
// BLOCK CARD - With separate OUT/IN tap handlers
// ============================================================
class _BlockCard extends StatelessWidget {
  const _BlockCard({
    required this.block,
    required this.status,
    required this.selected,
    required this.wireSrc,
    this.note,
    required this.isWireTarget,
    required this.onTapOutput,
    required this.onTapInput,
    required this.paletteBlocks,
  });

  final Map<String, dynamic> block;
  final List<dynamic> paletteBlocks;
  final String status;
  final bool selected, wireSrc, isWireTarget;
  final String? note;
  final void Function(String) onTapOutput;
  final VoidCallback onTapInput;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sc = _statusColor(status, isDark);
    final name = block['display_name']?.toString().isNotEmpty == true
        ? block['display_name'].toString()
        : block['block_id']?.toString() ?? 'Block';
    final tools = (block['config'] as Map?)?['tools'] as List? ?? [];

    final cardBg = isDark
        ? const Color(0xFF141422).withValues(alpha: 0.92)
        : Colors.white.withValues(alpha: 0.95);

    final borderColor = wireSrc
        ? const Color(0xFFF59E0B)
        : isWireTarget
            ? const Color(0xFF3B82F6)
            : selected
                ? const Color(0xFF6366F1)
                : (isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1));

    return Container(
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: borderColor,
          width: selected || wireSrc || isWireTarget ? 2 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.35 : 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: sc.withValues(alpha: isDark ? 0.15 : 0.08),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(13)),
              border: Border(
                bottom: BorderSide(
                  color: isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.05),
                ),
              ),
            ),
            child: Row(
              children: [
                Icon(_iconFor(block), size: 16, color: sc),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: isDark ? Colors.white : Colors.black87,
                    ),
                  ),
                ),
                if (selected)
                  const Icon(Icons.check_circle_rounded, size: 16, color: Color(0xFF6366F1)),
                if (wireSrc) ...[
                  const SizedBox(width: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF59E0B).withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'SRC',
                      style: TextStyle(
                        fontSize: 8,
                        color: Color(0xFFF59E0B),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
          // Content
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (tools.isNotEmpty) ...[
                    Wrap(
                      spacing: 4,
                      runSpacing: 2,
                      children: tools
                          .take(3)
                          .map((t) => Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: isDark
                                      ? Colors.white.withValues(alpha: 0.06)
                                      : Colors.black.withValues(alpha: 0.04),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '$t',
                                  style: TextStyle(
                                    fontSize: 9,
                                    color: isDark ? Colors.white70 : Colors.black87,
                                  ),
                                ),
                              ))
                          .toList(),
                    ),
                    const SizedBox(height: 4),
                  ],
                  Text(
                    _preview(block),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 10,
                      color: isDark ? Colors.white54 : Colors.black54,
                    ),
                  ),
                  if (note != null && note!.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.sticky_note_2_rounded, size: 10, color: Colors.amber),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            note!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 9,
                              color: isDark ? Colors.amber.shade300 : Colors.amber.shade800,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          // Footer Port Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: isDark ? Colors.black.withValues(alpha: 0.2) : Colors.black.withValues(alpha: 0.03),
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(13)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                // IN port
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Row(
                    children: [
                      GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTap: onTapInput,
                        child: Tooltip(
                          message: isWireTarget ? 'Click to connect here' : 'Input port',
                          child: Container(
                            padding: const EdgeInsets.all(3),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: isWireTarget ? Colors.blue.withValues(alpha: 0.25) : null,
                              border: isWireTarget
                                  ? Border.all(color: Colors.blue, width: 2)
                                  : Border.all(color: Colors.blue.withValues(alpha: 0.4), width: 1),
                            ),
                            child: const _Dot(color: Colors.blue, size: 7),
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      Text('IN', style: TextStyle(fontSize: 8.5, fontWeight: FontWeight.w600, color: isDark ? Colors.white38 : Colors.black38)),
                    ],
                  ),
                ),
                const Spacer(),
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(status.toUpperCase(), style: TextStyle(fontSize: 8, fontWeight: FontWeight.bold, color: sc)),
                ),
                const Spacer(),
                // OUT ports
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: (() {
                    // Try to get ports from palette definition first (static/structural ports)
                    final pBlock = paletteBlocks.firstWhere((p) => p['id'] == block['block_id'], orElse: () => null) as Map?;
                    if (pBlock != null && pBlock['output_ports'] != null) {
                      final ports = (pBlock['output_ports'] as List).map((p) => (p as Map)['name']?.toString() ?? 'output').toList();
                      if (ports.isNotEmpty) return ports;
                    }
                    // Fallback to instance config or default
                    final configPorts = (block['config'] as Map?)?['output_ports'] as List?;
                    if (configPorts != null && configPorts.isNotEmpty) {
                      return configPorts.map((e) => e.toString()).toList();
                    }
                    return ['output'];
                  })()
                      .map((portName) {
                    final isThisPortSrc = wireSrc;
                    return Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Row(
                        children: [
                          Text(portName == 'output' ? 'OUT' : portName.toUpperCase(), style: TextStyle(fontSize: 8.5, fontWeight: FontWeight.w600, color: isDark ? Colors.white38 : Colors.black38)),
                          const SizedBox(width: 4),
                          GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTap: () => onTapOutput(portName),
                            child: Tooltip(
                              message: isThisPortSrc ? 'Click again to cancel' : 'Click to start wire',
                              child: Container(
                                padding: const EdgeInsets.all(3),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: isThisPortSrc ? Colors.orange.withValues(alpha: 0.25) : null,
                                  border: isThisPortSrc
                                      ? Border.all(color: Colors.orange, width: 2)
                                      : Border.all(color: Colors.green.withValues(alpha: 0.4), width: 1),
                                ),
                                child: _Dot(
                                  color: isThisPortSrc ? Colors.orange : const Color(0xFF22C55E),
                                  size: 7,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color, this.size = 10});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => DecoratedBox(
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: SizedBox.square(dimension: size));
}

class _EndPoint extends StatelessWidget {
  const _EndPoint({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
  });

  final IconData icon;
  final String title, subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: 180,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF141422).withValues(alpha: 0.9) : Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.8), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: isDark ? 0.2 : 0.08),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.6,
                    color: color,
                  ),
                ),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark ? Colors.white54 : Colors.black54,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _WireBar extends StatelessWidget {
  const _WireBar({
    required this.wire,
    required this.onDelete,
    required this.onClear,
  });

  final Map<String, dynamic> wire;
  final VoidCallback onDelete, onClear;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF141422).withValues(alpha: 0.95) : Colors.white.withValues(alpha: 0.95),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.1),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.08),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: [
              const Icon(Icons.cable_rounded, size: 18, color: Color(0xFF6366F1)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${wire['source_step_id'] ?? '?'}:${wire['source_port'] ?? 'out'} \u2192 ${wire['target_step_id'] ?? '?'}:${wire['target_port'] ?? 'in'}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: isDark ? Colors.white : Colors.black87,
                  ),
                ),
              ),
              if (wire['label'] != null) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${wire['label']}',
                    style: const TextStyle(fontSize: 10, color: Color(0xFF6366F1), fontWeight: FontWeight.w600),
                  ),
                ),
              ],
              const SizedBox(width: 8),
              IconButton(
                tooltip: 'Disconnect',
                onPressed: () {
                  HapticFeedback.mediumImpact();
                  onDelete();
                },
                icon: const Icon(Icons.link_off_rounded, size: 18, color: Colors.redAccent),
                visualDensity: VisualDensity.compact,
              ),
              IconButton(
                tooltip: 'Close',
                onPressed: () {
                  HapticFeedback.selectionClick();
                  onClear();
                },
                icon: Icon(Icons.close_rounded, size: 18, color: isDark ? Colors.white54 : Colors.black54),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
        ),
      ),
    );
  }
}



class _WorkflowPicker extends StatelessWidget {
  const _WorkflowPicker({required this.items, required this.selectedId});
  final List<dynamic> items;
  final String? selectedId;
  @override
  Widget build(BuildContext context) => ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) {
        final w = Map<String, dynamic>.from(items[i] as Map);
        return ListTile(
            selected: w['draft_id']?.toString() == selectedId,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            tileColor: Theme.of(context).colorScheme.surface,
            leading: const Icon(Icons.account_tree_rounded),
            title: Text('${w['name'] ?? 'Workflow'}',
                overflow: TextOverflow.ellipsis),
            subtitle: Text(
                '${w['status'] ?? 'draft'} \u2022 ${(w['blocks'] as List?)?.length ?? 0} blocks'),
            onTap: () {
              HapticFeedback.selectionClick();
              Navigator.pop(context, w);
            });
      });
}

class _EmptyCanvas extends StatelessWidget {
  const _EmptyCanvas({required this.onCreate});
  final VoidCallback onCreate;
  @override
  Widget build(BuildContext context) => Stack(children: [
        const Positioned.fill(child: ColoredBox(color: Colors.black12)),
        Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.account_tree_rounded,
              size: 64, color: Colors.white38),
          const SizedBox(height: 16),
          const Text('No workflows yet',
              style: TextStyle(color: Colors.white54, fontSize: 18)),
          const SizedBox(height: 24),
          FilledButton.icon(
              onPressed: onCreate,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Create your first workflow'))
        ]))
      ]);
}

class _BlockDetails extends ConsumerStatefulWidget {
  const _BlockDetails(
      {required this.block,
      required this.status,
      required this.output,
      required this.wires,
      required this.onConnect,
      required this.onDelWires,
      required this.onDel,
      required this.onConfigChanged,
      required this.onAddNote});
  final Map<String, dynamic> block;
  final String status;
  final Map<String, dynamic>? output;
  final List<Map<String, dynamic>> wires;
  final VoidCallback onConnect, onDelWires, onDel;
  final ValueChanged<Map<String, dynamic>> onConfigChanged;
  final ValueChanged<String> onAddNote;

  @override
  ConsumerState<_BlockDetails> createState() => _BlockDetailsState();
}

class _BlockDetailsState extends ConsumerState<_BlockDetails> {
  late final TextEditingController _noteCtrl;

  @override
  void initState() {
    super.initState();
    _noteCtrl = TextEditingController(text: widget.block['note']?.toString() ?? '');
  }

  @override
  void didUpdateWidget(covariant _BlockDetails oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.block['note'] != widget.block['note']) {
      _noteCtrl.text = widget.block['note']?.toString() ?? '';
    }
  }

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final block = widget.block;
    final status = widget.status;
    final wires = widget.wires;
    final output = widget.output;
    final cs = Theme.of(context).colorScheme;

    final bid = block['block_id']?.toString() ?? 'Block';
    final sid = block['step_id']?.toString() ?? 'step';
    final config = Map<String, dynamic>.from(block['config'] as Map? ?? {});
    final tools = (config['tools'] as List? ?? []).map((e) => e.toString()).toList();
    final name = block['display_name']?.toString().isNotEmpty == true
        ? block['display_name'].toString()
        : bid;

    return Padding(
        padding: EdgeInsets.fromLTRB(
            16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 18),
        child: ListView(shrinkWrap: true, children: [
          Row(children: [
            Icon(_iconFor(block), color: _statusColor(status, Theme.of(context).brightness == Brightness.dark), size: 28),
            const SizedBox(width: 10),
            Expanded(
                child:
                    Text(name, style: Theme.of(context).textTheme.titleLarge))
          ]),
          const SizedBox(height: 6),
          Text('$sid \u2022 $status',
              style: Theme.of(context).textTheme.labelMedium),
          const Divider(height: 20),
          TextField(
              controller: _noteCtrl,
              decoration: const InputDecoration(
                  labelText: 'Note',
                  hintText: 'Add a note...',
                  prefixIcon: Icon(Icons.sticky_note_2_rounded),
                  border: OutlineInputBorder()),
              onChanged: widget.onAddNote,
              minLines: 1,
              maxLines: 2),
          const SizedBox(height: 12),
          if (tools.isNotEmpty)
            _Section(title: 'RIP Tools (${tools.length})', lines: tools),
          _Section(
              title: 'Input Bindings',
              lines: _mapLines(block['input_bindings'])),
          _ConfigForm(
            schema: _schemaProps(_schemaMap(block['config_schema'])),
            config: config,
            onChanged: (k, v) {
              final newConfig = Map<String, dynamic>.from(config);
              newConfig[k] = v;
              widget.onConfigChanged(newConfig);
            },
          ),
          if (wires.isNotEmpty)
            _Section(
                title: 'Wires (${wires.length})',
                lines: wires
                    .map((w) =>
                        '${w['source_step_id'] ?? '?'} \u2192 ${w['target_step_id'] ?? '?'}${w['label'] != null ? ' [${w['label']}]' : ''}')
                    .toList()),
          if (output != null)
            _Section(title: 'Last Output', lines: _mapLines(output)),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.icon(
                onPressed: widget.onConnect,
                icon: const Icon(Icons.cable_rounded),
                label: const Text('Connect')),
            OutlinedButton.icon(
                onPressed: wires.isEmpty ? null : widget.onDelWires,
                icon: const Icon(Icons.link_off_rounded),
                label: const Text('Disconnect All')),
            OutlinedButton.icon(
                onPressed: widget.onDel,
                icon: const Icon(Icons.delete_outline_rounded),
                label: const Text('Delete'),
                style: OutlinedButton.styleFrom(foregroundColor: cs.error))
          ])
        ]));
  }
}

class _ConfigForm extends StatelessWidget {
  const _ConfigForm({required this.schema, required this.config, required this.onChanged});
  final Map<String, dynamic> schema;
  final Map<String, dynamic> config;
  final void Function(String, dynamic) onChanged;

  @override
  Widget build(BuildContext context) {
    if (schema.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 12),
          child: Text('Configuration', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        ),
        ...schema.entries.map((e) {
          final k = e.key;
          final prop = e.value is Map ? e.value as Map<String, dynamic> : <String, dynamic>{};
          final type = prop['type']?.toString() ?? 'string';
          final title = prop['title']?.toString() ?? _fieldLabel(k);
          final desc = prop['description']?.toString();
          
          if (type == 'boolean') {
            return SwitchListTile(
              title: Text(title),
              subtitle: desc != null ? Text(desc) : null,
              value: config[k] == true || config[k] == 'true',
              onChanged: (v) => onChanged(k, v),
              contentPadding: EdgeInsets.zero,
            );
          } else if (prop.containsKey('enum')) {
            final options = (prop['enum'] as List?)?.map((o) => o.toString()).toList() ?? [];
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: DropdownButtonFormField<String>(
                decoration: InputDecoration(labelText: title, helperText: desc, border: const OutlineInputBorder()),
                value: config[k]?.toString(),
                items: options.map((o) => DropdownMenuItem(value: o, child: Text(o))).toList(),
                onChanged: (v) {
                  if (v != null) onChanged(k, v);
                },
              ),
            );
          } else {
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: TextFormField(
                initialValue: config[k]?.toString() ?? '',
                decoration: InputDecoration(labelText: title, helperText: desc, border: const OutlineInputBorder()),
                onChanged: (v) => onChanged(k, v),
              ),
            );
          }
        }),
        const Divider(),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.lines});
  final String title;
  final List<String> lines;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        if (lines.isEmpty)
          Text('None',
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: Colors.grey))
        else
          ...lines.map((l) => Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: Theme.of(context)
                          .colorScheme
                          .surfaceContainerHighest
                          .withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(6)),
                  child: SelectableText(l,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(fontFamily: 'monospace')))))
      ]));
}

// ============================================================
// QUICK CONFIG
// ============================================================
class _Configured {
  final Map<String, dynamic> config, bindings;
  const _Configured({required this.config, required this.bindings});
}

class _QuickConfigSheet {
  static Future<_Configured?> show(BuildContext ctx, Map<String, dynamic> block,
      List<Map<String, dynamic>> existing, WidgetRef ref) {
    final bid = block['id']?.toString() ?? '';
    return showModalBottomSheet<_Configured>(
        context: ctx,
        isScrollControlled: true,
        showDragHandle: true,
        builder: (_) {
          if (bid.toLowerCase().contains('rip') ||
              bid.toLowerCase().contains('context')) return _RIPQuickConfig();
          if (bid == 'prompt.ask_ai') return _PromptQuickConfig(ref: ref);
          if (bid.contains('approval')) return _ApprovalQuickConfig();
          if (bid.contains('terminal')) return _TerminalQuickConfig();
          if (bid.contains('notification')) return _NotificationQuickConfig();
          return _GenericQuickConfig(block: block);
        });
  }
}

class _RIPQuickConfig extends StatefulWidget {
  const _RIPQuickConfig();
  @override
  State<_RIPQuickConfig> createState() => _RIPQuickConfigState();
}

class _RIPQuickConfigState extends State<_RIPQuickConfig> {
  final _tools = const [
    {'name': 'search', 'desc': 'Semantic search across the codebase'},
    {'name': 'trace', 'desc': 'Trace dependency chains'},
    {'name': 'explain', 'desc': 'Explain architecture and code structure'},
    {'name': 'impact', 'desc': 'Analyze impact of proposed changes'},
    {'name': 'architecture', 'desc': 'Generate architecture overview'},
    {'name': 'metrics', 'desc': 'Code metrics and complexity'},
    {'name': 'dead_code', 'desc': 'Detect unused functions and classes'},
    {'name': 'onboard', 'desc': 'Generate onboarding guides'}
  ];
  final _selected = <String>{};
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
        padding: EdgeInsets.fromLTRB(
            16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                const Icon(Icons.search_rounded, color: Color(0xFF8B5CF6)),
                const SizedBox(width: 10),
                Expanded(
                    child: Text('RIP Intelligence',
                        style: Theme.of(context).textTheme.titleLarge))
              ]),
              const SizedBox(height: 12),
              Row(children: [
                TextButton.icon(
                    onPressed: () => setState(() =>
                        _selected.addAll(_tools.map((t) => '${t['name']}'))),
                    icon: const Icon(Icons.select_all_rounded, size: 16),
                    label: const Text('All')),
                TextButton.icon(
                    onPressed: () => setState(() => _selected.clear()),
                    icon: const Icon(Icons.deselect_rounded, size: 16),
                    label: const Text('Clear')),
                const Spacer(),
                Text('${_selected.length} selected')
              ]),
              const SizedBox(height: 6),
              Flexible(
                  child: ListView(
                      shrinkWrap: true,
                      children: _tools.map((t) {
                        final name = '${t['name']}',
                            sel = _selected.contains(name);
                        return Card(
                            margin: const EdgeInsets.only(bottom: 4),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                                side: BorderSide(
                                    color: sel
                                        ? const Color(0xFF8B5CF6)
                                        : cs.outlineVariant,
                                    width: sel ? 2 : 1)),
                            child: InkWell(
                                borderRadius: BorderRadius.circular(8),
                                onTap: () => setState(() => sel
                                    ? _selected.remove(name)
                                    : _selected.add(name)),
                                child: Padding(
                                    padding: const EdgeInsets.all(10),
                                    child: Row(children: [
                                      Container(
                                          width: 20,
                                          height: 20,
                                          decoration: BoxDecoration(
                                              shape: BoxShape.circle,
                                              color: sel
                                                  ? const Color(0xFF8B5CF6)
                                                  : Colors.transparent,
                                              border: Border.all(
                                                  color: sel
                                                      ? const Color(0xFF8B5CF6)
                                                      : cs.outline,
                                                  width: 2)),
                                          child: sel
                                              ? const Icon(Icons.check_rounded,
                                                  size: 12, color: Colors.white)
                                              : null),
                                      const SizedBox(width: 10),
                                      Expanded(
                                          child: Column(
                                              crossAxisAlignment:
                                                  CrossAxisAlignment.start,
                                              children: [
                                            Text(name,
                                                style: Theme.of(context)
                                                    .textTheme
                                                    .titleSmall),
                                            Text('${t['desc']}',
                                                style: Theme.of(context)
                                                    .textTheme
                                                    .bodySmall
                                                    ?.copyWith(fontSize: 10))
                                          ]))
                                    ]))));
                      }).toList())),
              const SizedBox(height: 12),
              FilledButton.icon(
                  onPressed: _selected.isEmpty
                      ? null
                      : () => Navigator.pop(
                          context,
                          _Configured(config: {
                            'tools': _selected.toList()
                          }, bindings: {
                            'query': {'source': 'trigger_query'}
                          })),
                  icon: const Icon(Icons.check_rounded),
                  label: Text(
                      'Add ${_selected.length} tool${_selected.length == 1 ? '' : 's'}'))
            ]));
  }
}

class _PromptQuickConfig extends ConsumerStatefulWidget {
  const _PromptQuickConfig({required this.ref});
  final WidgetRef ref;
  @override
  ConsumerState<_PromptQuickConfig> createState() => _PromptQuickConfigState();
}

class _PromptQuickConfigState extends ConsumerState<_PromptQuickConfig> {
  String? _pid;
  String _selectedModel = 'primary';
  List<Map<String, dynamic>> _llmConfigs = [];
  final _quick = TextEditingController();
  List<Map<String, dynamic>> _cachedTemplates = [];
  bool _loaded = false;
  bool _llmLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([_loadTemplates(), _loadLLM()]);
  }

  Future<void> _loadTemplates() async {
    try {
      final data = await widget.ref.read(ripClientProvider).listGatewayPromptTemplates();
      if (!mounted) return;
      setState(() {
        _cachedTemplates = ((data['templates'] as List?) ?? [])
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
        _loaded = true;
      });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  Future<void> _loadLLM() async {
    try {
      final data = await widget.ref.read(ripClientProvider).listLLMConfigs();
      if (!mounted) return;
      setState(() {
        _llmConfigs = ((data['configs'] as List?) ?? [])
            .whereType<Map>()
            .map((m) => Map<String, dynamic>.from(m))
            .toList();
        _llmLoaded = true;
        if (_selectedModel == 'primary' && _llmConfigs.isNotEmpty) {
          _selectedModel = _llmConfigs.first['id']?.toString() ?? 'primary';
        }
      });
    } catch (_) {
      if (mounted) setState(() => _llmLoaded = true);
    }
  }

  Future<void> _showAddModelDialog() async {
    final nameCtrl = TextEditingController();
    final providerCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final keyCtrl = TextEditingController();
    final urlCtrl = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add LLM Model'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Name *',
                  hintText: 'my-gpt4',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: providerCtrl,
                decoration: const InputDecoration(
                  labelText: 'Provider *',
                  hintText: 'openai, anthropic, google, openrouter, ollama',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: modelCtrl,
                decoration: const InputDecoration(
                  labelText: 'Model *',
                  hintText: 'gpt-4, claude-3-5-sonnet, gemini-2.5-flash',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: keyCtrl,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'API Key',
                  hintText: 'sk-... (leave empty for local models)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: urlCtrl,
                decoration: const InputDecoration(
                  labelText: 'Base URL (optional)',
                  hintText: 'https://api.openai.com/v1',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Add Model'),
          ),
        ],
      ),
    );

    nameCtrl.dispose();
    providerCtrl.dispose();
    modelCtrl.dispose();
    keyCtrl.dispose();
    urlCtrl.dispose();

    if (result != true || !mounted) return;

    final name = nameCtrl.text.trim();
    final provider = providerCtrl.text.trim();
    final model = modelCtrl.text.trim();
    final apiKey = keyCtrl.text.trim();
    final baseUrl = urlCtrl.text.trim();

    if (name.isEmpty || provider.isEmpty || model.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Name, provider, and model are required')),
        );
      }
      return;
    }

    try {
      await widget.ref.read(ripClientProvider).addLLMConfig(
        configId: name,
        provider: provider,
        model: model,
        apiKey: apiKey.isEmpty ? null : apiKey,
        baseUrl: baseUrl.isEmpty ? null : baseUrl,
      );
      await _loadLLM();
      setState(() => _selectedModel = name);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Model "$name" added')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to add model: $e')),
        );
      }
    }
  }

  @override
  void dispose() {
    _quick.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('AI Analysis', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          if (!_loaded)
            const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
          else ...[
            Flexible(
              child: _cachedTemplates.isEmpty
                  ? const Text('No templates yet.')
                  : ListView(
                      shrinkWrap: true,
                      children: [
                        Text('Saved Templates', style: Theme.of(context).textTheme.titleSmall),
                        const SizedBox(height: 6),
                        for (final t in _cachedTemplates) _buildTemplateCard(t, cs),
                      ],
                    ),
            ),
            // LLM Model Selector
            const SizedBox(height: 12),
            Row(children: [
              Text('Model', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              TextButton.icon(
                onPressed: _showAddModelDialog,
                icon: const Icon(Icons.add_rounded, size: 16),
                label: const Text('Add Model'),
              ),
            ]),
            if (_llmLoaded && _llmConfigs.isNotEmpty) ...[
              const SizedBox(height: 4),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  for (final cfg in _llmConfigs)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(
                          '${cfg['provider']}/${cfg['model']}',
                          style: const TextStyle(fontSize: 11),
                        ),
                        selected: _selectedModel == cfg['id']?.toString(),
                        onSelected: (sel) {
                          if (sel) setState(() => _selectedModel = cfg['id']?.toString() ?? 'primary');
                        },
                        avatar: cfg['has_api_key'] == true
                            ? const Icon(Icons.vpn_key_rounded, size: 14)
                            : null,
                      ),
                    ),
                ]),
              ),
            ] else if (_llmLoaded)
              Padding(
                padding: const EdgeInsets.all(8),
                child: Text('No models configured. Add one using the button above.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey)),
              ),
            const Divider(height: 20),
            TextField(
              controller: _quick,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Quick Prompt', hintText: 'Analyze this code...', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: () {
                final b = <String, dynamic>{'query': {'source': 'trigger_query'}};
                b['model_preference'] = {'source': 'literal', 'value': _selectedModel};
                if (_pid != null) {
                  b['prompt_id'] = {'source': 'literal', 'value': _pid};
                } else if (_quick.text.trim().isNotEmpty) {
                  b['prompt'] = {'source': 'literal', 'value': _quick.text.trim()};
                } else {
                  return;
                }
                Navigator.pop(context, _Configured(config: {}, bindings: b));
              },
              icon: const Icon(Icons.check_rounded),
              label: const Text('Add Block'),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTemplateCard(Map<String, dynamic> t, ColorScheme cs) {
    final tid = t['id']?.toString() ?? '';
    final sel = _pid == tid;
    final preview = (t['prompt_template'] ?? t['template'] ?? '').toString();
    final short = preview.length > 60 ? '${preview.substring(0, 60)}...' : preview;
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: sel ? cs.primary : cs.outlineVariant, width: sel ? 2 : 1)),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => setState(() => _pid = sel ? null : tid),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(children: [
            Container(width: 20, height: 20, decoration: BoxDecoration(shape: BoxShape.circle, color: sel ? cs.primary : Colors.transparent, border: Border.all(color: sel ? cs.primary : cs.outline, width: 2)), child: sel ? Icon(Icons.check_rounded, size: 12, color: cs.onPrimary) : null),
            const SizedBox(width: 10),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${t['name'] ?? 'Untitled'}', style: Theme.of(context).textTheme.titleSmall), Text(short, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall?.copyWith(fontSize: 10))])),
          ]),
        ),
      ),
    );
  }
}
class _ApprovalQuickConfig extends StatefulWidget {
  const _ApprovalQuickConfig();
  @override
  State<_ApprovalQuickConfig> createState() => _ApprovalQuickConfigState();
}

class _ApprovalQuickConfigState extends State<_ApprovalQuickConfig> {
  String _when = 'always';
  @override
  Widget build(BuildContext context) => Padding(
      padding: EdgeInsets.fromLTRB(
          16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Approval Gate',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Column(
              children: [
                ListTile(
                  title: const Text('Always pause'),
                  leading: Radio<String>(
                    value: 'always',
                    groupValue: _when,
                    onChanged: (v) => setState(() => _when = v!),
                  ),
                  dense: true,
                  onTap: () => setState(() => _when = 'always'),
                ),
                ListTile(
                  title: const Text('If high risk'),
                  leading: Radio<String>(
                    value: 'risk',
                    groupValue: _when,
                    onChanged: (v) => setState(() => _when = v!),
                  ),
                  dense: true,
                  onTap: () => setState(() => _when = 'risk'),
                ),
                ListTile(
                  title: const Text('Protected files'),
                  leading: Radio<String>(
                    value: 'protected',
                    groupValue: _when,
                    onChanged: (v) => setState(() => _when = v!),
                  ),
                  dense: true,
                  onTap: () => setState(() => _when = 'protected'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
                onPressed: () => Navigator.pop(context,
                    _Configured(config: {'condition': _when}, bindings: {})),
                icon: const Icon(Icons.check_rounded),
                label: const Text('Add Block'))
          ]));
}

class _TerminalQuickConfig extends StatefulWidget {
  const _TerminalQuickConfig();
  @override
  State<_TerminalQuickConfig> createState() => _TerminalQuickConfigState();
}

class _TerminalQuickConfigState extends State<_TerminalQuickConfig> {
  final _cmd = TextEditingController(text: 'pytest');
  @override
  void dispose() {
    _cmd.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: EdgeInsets.fromLTRB(
          16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Terminal', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            TextField(
                controller: _cmd,
                decoration: const InputDecoration(
                    labelText: 'Command',
                    hintText: 'pytest',
                    border: OutlineInputBorder())),
            const SizedBox(height: 12),
            FilledButton.icon(
                onPressed: _cmd.text.trim().isEmpty
                    ? null
                    : () => Navigator.pop(
                        context,
                        _Configured(
                            config: {'command': _cmd.text.trim()},
                            bindings: {})),
                icon: const Icon(Icons.check_rounded),
                label: const Text('Add Block'))
          ]));
}

class _NotificationQuickConfig extends StatefulWidget {
  const _NotificationQuickConfig();
  @override
  State<_NotificationQuickConfig> createState() =>
      _NotificationQuickConfigState();
}

class _NotificationQuickConfigState extends State<_NotificationQuickConfig> {
  String _channel = 'push';
  final _msg = TextEditingController(text: 'Workflow completed');
  @override
  void dispose() {
    _msg.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: EdgeInsets.fromLTRB(
          16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Notification', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            SegmentedButton<String>(segments: const [
              ButtonSegment(value: 'push', label: Text('Push')),
              ButtonSegment(value: 'in_app', label: Text('In-App'))
            ], selected: {
              _channel
            }, onSelectionChanged: (v) => setState(() => _channel = v.first)),
            const SizedBox(height: 10),
            TextField(
                controller: _msg,
                decoration: const InputDecoration(
                    labelText: 'Message', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            FilledButton.icon(
                onPressed: () => Navigator.pop(
                    context,
                    _Configured(config: {
                      'channel': _channel,
                      'message': _msg.text.trim()
                    }, bindings: {})),
                icon: const Icon(Icons.check_rounded),
                label: const Text('Add Block'))
          ]));
}

class _GenericQuickConfig extends StatefulWidget {
  const _GenericQuickConfig({required this.block});
  final Map<String, dynamic> block;
  @override
  State<_GenericQuickConfig> createState() => _GenericQuickConfigState();
}

class _GenericQuickConfigState extends State<_GenericQuickConfig> {
  final _bindings = <String, String>{};
  final _portSources = <String, String>{};
  final _config = <String, dynamic>{};

  @override
  void initState() {
    super.initState();
    final cProps = _schemaProps(_schemaMap(widget.block['config_schema']));
    for (final e in cProps.entries) {
      if (e.value is Map && e.value['default'] != null) {
        _config[e.key] = e.value['default'];
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final inputs = _schemaProps(_schemaMap(widget.block['input_schema']));
    final required = _schemaRequired(_schemaMap(widget.block['input_schema']));
    final cProps = _schemaProps(_schemaMap(widget.block['config_schema']));
    
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(widget.block['name']?.toString() ?? 'Block',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          Flexible(
            child: ListView(
              shrinkWrap: true,
              children: [
                if (inputs.isNotEmpty) ...[
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('Inputs', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  ),
                  ...inputs.keys.map((portName) {
                    final isReq = required.contains(portName);
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${_fieldLabel(portName)}${isReq ? ' *' : ''}',
                              style: Theme.of(context).textTheme.titleSmall),
                          const SizedBox(height: 4),
                          SegmentedButton<String>(
                            segments: [
                              ButtonSegment(value: 'chat', label: Text(isReq ? 'Chat' : 'Unused')),
                              ButtonSegment(value: 'literal', label: const Text('Value')),
                            ],
                            selected: {_portSources[portName] ?? (isReq ? 'chat' : 'unused')},
                            onSelectionChanged: (v) {
                              setState(() => _portSources[portName] = v.first);
                            },
                          ),
                          if (_portSources[portName] == 'literal')
                            TextField(
                              decoration: InputDecoration(
                                hintText: 'Enter value...',
                                border: const OutlineInputBorder(),
                              ),
                              onChanged: (v) => _bindings[portName] = v,
                            ),
                        ],
                      ),
                    );
                  }),
                ] else if (cProps.isEmpty)
                  Text('No inputs or configuration needed.', style: Theme.of(context).textTheme.bodySmall),
                if (cProps.isNotEmpty)
                  _ConfigForm(
                    schema: cProps,
                    config: _config,
                    onChanged: (k, v) => setState(() => _config[k] = v),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: () {
              final b = <String, dynamic>{};
              for (final k in inputs.keys) {
                final source = _portSources[k] ?? 'chat';
                if (source == 'unused') continue;
                b[k] = {
                  'source': source == 'literal' ? 'literal' : 'trigger_query',
                  if (source == 'literal' && (_bindings[k]?.isNotEmpty == true))
                    'value': _bindings[k],
                };
              }
              Navigator.pop(context, _Configured(config: _config, bindings: b));
            },
            icon: const Icon(Icons.check_rounded),
            label: const Text('Add Block'),
          ),
        ],
      ),
    );
  }
}

// Add this field to _GenericQuickConfigState:

class _BlockPalette extends StatefulWidget {
  const _BlockPalette({required this.blocks});
  final List<Map<String, dynamic>> blocks;

  @override
  State<_BlockPalette> createState() => _BlockPaletteState();
}

class _BlockPaletteState extends State<_BlockPalette> {
  final TextEditingController _searchCtrl = TextEditingController();
  String _selectedCategory = 'all';
  String _searchQuery = '';

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgSurface = isDark
        ? const Color(0xFF12121E).withValues(alpha: 0.96)
        : Colors.white.withValues(alpha: 0.98);

    final categories = ['all', 'trigger', 'retrieval', 'tool', 'prompt', 'approval', 'verification', 'deployment', 'notification', 'memory'];

    final filteredBlocks = widget.blocks.where((b) {
      final kind = b['kind']?.toString().toLowerCase() ?? 'other';
      if (_selectedCategory != 'all' && kind != _selectedCategory) return false;
      if (_searchQuery.trim().isEmpty) return true;
      final q = _searchQuery.toLowerCase();
      final name = (b['name'] ?? b['id'] ?? '').toString().toLowerCase();
      final desc = (b['description'] ?? '').toString().toLowerCase();
      final tools = (b['tools'] as List? ?? []).join(' ').toLowerCase();
      return name.contains(q) || desc.contains(q) || tools.contains(q);
    }).toList();

    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final b in filteredBlocks) {
      final kind = b['kind']?.toString() ?? 'other';
      grouped.putIfAbsent(kind, () => []).add(b);
    }

    return Container(
      height: MediaQuery.of(context).size.height * 0.78,
      decoration: BoxDecoration(
        color: bgSurface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.12) : Colors.black.withValues(alpha: 0.08),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.5 : 0.15),
            blurRadius: 24,
            offset: const Offset(0, -8),
          ),
        ],
      ),
      child: Column(
        children: [
          // Drag Handle
          const SizedBox(height: 10),
          Center(
            child: Container(
              width: 38,
              height: 4,
              decoration: BoxDecoration(
                color: isDark ? Colors.white24 : Colors.black26,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 12),
          // Title & Total Badge
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.add_box_rounded, color: Color(0xFF6366F1), size: 20),
                ),
                const SizedBox(width: 10),
                Text(
                  'Add Workflow Block',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                    color: isDark ? Colors.white : Colors.black87,
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
                  ),
                  child: Text(
                    '${filteredBlocks.length} Available',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF6366F1),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          // Hairline Search Field
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              height: 42,
              decoration: BoxDecoration(
                color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.04),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
                ),
              ),
              child: TextField(
                controller: _searchCtrl,
                style: TextStyle(fontSize: 13, color: isDark ? Colors.white : Colors.black87),
                onChanged: (v) => setState(() => _searchQuery = v),
                decoration: InputDecoration(
                  hintText: 'Search blocks, sources, or tools...',
                  hintStyle: TextStyle(fontSize: 13, color: isDark ? Colors.white38 : Colors.black38),
                  prefixIcon: Icon(Icons.search_rounded, size: 18, color: isDark ? Colors.white54 : Colors.black54),
                  suffixIcon: _searchQuery.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear_rounded, size: 16),
                          onPressed: () {
                            _searchCtrl.clear();
                            setState(() => _searchQuery = '');
                          },
                        )
                      : null,
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: 11),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          // Horizontal Category Filter Bar
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: categories.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (ctx, idx) {
                final cat = categories[idx];
                final isSel = _selectedCategory == cat;
                final title = cat == 'all' ? 'All Blocks' : _kindTitle(cat);
                return InkWell(
                  onTap: () {
                    HapticFeedback.selectionClick();
                    setState(() => _selectedCategory = cat);
                  },
                  borderRadius: BorderRadius.circular(10),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: isSel
                          ? const Color(0xFF6366F1)
                          : (isDark ? Colors.white.withValues(alpha: 0.06) : Colors.black.withValues(alpha: 0.04)),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isSel
                            ? const Color(0xFF6366F1)
                            : (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06)),
                      ),
                    ),
                    child: Text(
                      title,
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: isSel ? FontWeight.bold : FontWeight.w500,
                        color: isSel ? Colors.white : (isDark ? Colors.white70 : Colors.black87),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          const Divider(height: 1),
          // Grouped List
          Expanded(
            child: filteredBlocks.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.search_off_rounded, size: 42, color: isDark ? Colors.white24 : Colors.black26),
                        const SizedBox(height: 8),
                        Text(
                          'No matching blocks found',
                          style: TextStyle(
                            fontSize: 13,
                            color: isDark ? Colors.white54 : Colors.black54,
                          ),
                        ),
                      ],
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                    children: [
                      for (final entry in grouped.entries) ...[
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 8),
                          child: Row(
                            children: [
                              Icon(_kindIcon(entry.key), size: 16, color: const Color(0xFF6366F1)),
                              const SizedBox(width: 6),
                              Text(
                                _kindTitle(entry.key),
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 0.4,
                                  color: isDark ? Colors.white70 : Colors.black87,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                decoration: BoxDecoration(
                                  color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  '${entry.value.length}',
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w600,
                                    color: isDark ? Colors.white60 : Colors.black54,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        for (final b in entry.value) ...[
                          _buildBlockPaletteCard(context, b, isDark),
                          const SizedBox(height: 8),
                        ],
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildBlockPaletteCard(BuildContext context, Map<String, dynamic> b, bool isDark) {
    final name = '${b['name'] ?? b['id'] ?? 'Block'}';
    final desc = '${b['description'] ?? ''}';
    final tools = (b['tools'] as List? ?? []).map((t) => t.toString()).toList();
    final blockColor = _displayColor(b);
    final iconData = _iconFor(b);

    return InkWell(
      onTap: () {
        HapticFeedback.mediumImpact();
        Navigator.pop(context, b);
      },
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isDark ? Colors.white.withValues(alpha: 0.04) : Colors.black.withValues(alpha: 0.02),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isDark ? Colors.white.withValues(alpha: 0.07) : Colors.black.withValues(alpha: 0.06),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon Container
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: blockColor.withValues(alpha: isDark ? 0.2 : 0.1),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: blockColor.withValues(alpha: 0.3)),
              ),
              child: Icon(iconData, color: blockColor, size: 20),
            ),
            const SizedBox(width: 12),
            // Information Column
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          style: TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                            color: isDark ? Colors.white : Colors.black87,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(
                          color: const Color(0xFF6366F1).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: const [
                            Icon(Icons.add_rounded, size: 12, color: Color(0xFF6366F1)),
                            SizedBox(width: 2),
                            Text(
                              'Add',
                              style: TextStyle(
                                fontSize: 10.5,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF6366F1),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  if (desc.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      desc,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11,
                        height: 1.3,
                        color: isDark ? Colors.white60 : Colors.black54,
                      ),
                    ),
                  ],
                  if (tools.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: tools.take(4).map((t) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: isDark ? Colors.white.withValues(alpha: 0.07) : Colors.black.withValues(alpha: 0.04),
                            borderRadius: BorderRadius.circular(5),
                            border: Border.all(
                              color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.05),
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.build_circle_outlined, size: 10, color: blockColor),
                              const SizedBox(width: 3),
                              Text(
                                t,
                                style: TextStyle(
                                  fontSize: 9.5,
                                  fontWeight: FontWeight.w500,
                                  color: isDark ? Colors.white70 : Colors.black87,
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// HELPERS
// ============================================================
List<Map<String, dynamic>> _blocks(Map<String, dynamic> w) =>
    (w['blocks'] as List? ?? [])
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
List<Map<String, dynamic>> _wires(Map<String, dynamic> w) =>
    (w['wires'] as List? ?? [])
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
Offset _pos(Map<String, dynamic> b) {
  final p = b['position'] as Map?;
  return Offset((p?['x'] as num?)?.toDouble() ?? 120,
      (p?['y'] as num?)?.toDouble() ?? 180);
}

Map<String, double> _nextPos(Map<String, dynamic> w) {
  final blocks = _blocks(w);
  if (blocks.isEmpty) return const {'x': 160, 'y': 220};
  final positions = blocks.map(_pos).toList();
  final r = positions.reduce((a, b) => a.dx >= b.dx ? a : b);
  return r.dx + 280 <= 17200
      ? {'x': r.dx + 280, 'y': r.dy}
      : {
          'x': 160,
          'y': positions.map((o) => o.dy).reduce((a, b) => a > b ? a : b) + 200
        };
}

String _stepStatus(Map<String, dynamic>? s, String? id) {
  if (id == null || s == null) return 'ready';
  final st = (s['step_states'] as Map?)?[id];
  return st is Map ? '${st['status'] ?? 'ready'}' : 'ready';
}

Map<String, dynamic>? _stepOutput(Map<String, dynamic>? s, String? id) {
  if (id == null || s == null) return null;
  final st = (s['step_states'] as Map?)?[id];
  if (st is Map) {
    final o = st['output'];
    if (o is Map) return Map<String, dynamic>.from(o);
  }
  return null;
}

List<String> _mapLines(Object? v) {
  if (v == null) return const [];
  if (v is Map)
    return v.isEmpty
        ? const []
        : v.entries.map((e) => '${e.key}: ${e.value}').toList();
  if (v is List) return v.isEmpty ? const [] : v.map((i) => '$i').toList();
  return ['$v'];
}

Map<String, dynamic> _schemaMap(Object? v) =>
    v is Map ? Map<String, dynamic>.from(v) : const {};
Map<String, dynamic> _schemaProps(Map<String, dynamic> s) =>
    s['properties'] is Map
        ? Map<String, dynamic>.from(s['properties'])
        : const {};
        // Add these near the other _schema functions (around line 3050)

String _schemaType(Map<String, dynamic> schema) {
  final type = schema['type'];
  if (type is List && type.isNotEmpty) return type.first.toString();
  return type?.toString() ?? 'string';
}

String _schemaHint(Map<String, dynamic> schema) {
  final description = schema['description']?.toString();
  if (description != null && description.isNotEmpty) return description;
  final type = _schemaType(schema);
  return switch (type) {
    'array' => 'Enter a JSON array.',
    'object' => 'Enter a JSON object.',
    'number' || 'integer' => 'Enter a number.',
    'boolean' => 'Enter true or false.',
    _ => 'Enter text.',
  };
}

Set<String> _schemaRequired(Map<String, dynamic> schema) {
  final required = schema['required'];
  if (required is List) {
    return required.map((item) => item.toString()).toSet();
  }
  return const <String>{};
}


String? _missingStep(Map<String, dynamic>? s) {
  final m = s?['missing_inputs'] as Map?;
  return m?.isEmpty == false ? m!.keys.first.toString() : null;
}

bool _hasStatus(Map<String, dynamic>? s, String st) =>
    (s?['step_states'] as Map? ?? {})
        .values
        .any((x) => x is Map && x['status'] == st);
PipelineTrace _makeTrace(String rid, Map<String, dynamic> s) {
  final steps =
      (s['step_states'] as Map? ?? {}).values.whereType<Map>().toList();
  var seq = 0;
  return PipelineTrace(sessionId: rid, events: [
    ...steps.map((st) => PipelineEvent(
        sessionId: rid,
        stage: st['block_id']?.toString() ?? 'step',
        status: st['status'] == 'completed'
            ? 'done'
            : '${st['status'] ?? 'pending'}',
        detail: '${st['block_id'] ?? 'Step'}: ${st['status'] ?? 'pending'}',
        meta: {if (st['error'] != null) 'error': st['error']},
        seq: ++seq,
        timestamp: DateTime.tryParse(st['completed_at']?.toString() ?? '') ??
            DateTime.now())),
    if (s['final_output'] != null)
      PipelineEvent(
          sessionId: rid,
          stage: 'done',
          status: 'done',
          detail: 'Completed',
          meta: const {},
          seq: ++seq,
          timestamp: DateTime.now())
  ]);
}

String _preview(Map<String, dynamic> b) {
  final bindings = b['input_bindings'] as Map? ?? const {};
  if (bindings.isEmpty) return 'From chat input';
  return bindings.entries
      .take(2)
      .map(
          (e) => '${e.key}: ${e.value is Map ? e.value['source'] ?? '?' : '?'}')
      .join('\n');
}

Color _statusColor(String s, bool isDark) => switch (s) {
      'running' => const Color(0xFF6366F1),
      'completed' => const Color(0xFF22C55E),
      'failed' => const Color(0xFFEF4444),
      'awaiting_input' || 'awaiting_approval' => const Color(0xFFF59E0B),
      _ => isDark ? Colors.white38 : Colors.black38,
    };
IconData _iconFor(Map<String, dynamic> b) {
  final id = (b['block_id'] ?? b['id'] ?? '')?.toString().toLowerCase() ?? '';
  final name = (b['display_name'] ?? b['name'] ?? '')?.toString().toLowerCase() ?? '';
  final kind = (b['kind'] ?? '')?.toString().toLowerCase() ?? '';
  final combined = '$id $name $kind';

  if (combined.contains('condition') || combined.contains('if/else')) return Icons.alt_route_rounded;
  if (combined.contains('for_each') || combined.contains('loop')) return Icons.loop_rounded;
  if (combined.contains('parallel') || combined.contains('fan-out')) return Icons.flash_on_rounded;
  if (combined.contains('subworkflow')) return Icons.account_tree_rounded;
  if (combined.contains('wait_for_signal') || combined.contains('signal')) return Icons.hourglass_bottom_rounded;
  if (combined.contains('cron') || combined.contains('schedule')) return Icons.access_time_filled_rounded;
  if (combined.contains('webhook')) return Icons.webhook_rounded;
  if (combined.contains('file_watch')) return Icons.remove_red_eye_rounded;
  if (combined.contains('transform')) return Icons.transform_rounded;
  if (combined.contains('vector_write') || combined.contains('memory')) return Icons.memory_rounded;
  if (combined.contains('agent')) return Icons.smart_toy_rounded;
  if (combined.contains('approval') || combined.contains('gate')) return Icons.verified_user_rounded;
  if (combined.contains('terminal') || combined.contains('cmd') || combined.contains('shell')) return Icons.terminal_rounded;
  if (combined.contains('github') || combined.contains('git')) return Icons.account_tree_rounded;
  if (combined.contains('prompt') || combined.contains('llm') || combined.contains('ai') || combined.contains('gpt')) return Icons.psychology_rounded;
  if (combined.contains('notification') || combined.contains('slack') || combined.contains('alert')) return Icons.notifications_rounded;
  if (combined.contains('search') || combined.contains('retrieval') || combined.contains('context') || combined.contains('rip') || combined.contains('vector')) return Icons.saved_search_rounded;
  if (combined.contains('db') || combined.contains('database') || combined.contains('sql') || combined.contains('postgres')) return Icons.storage_rounded;
  if (combined.contains('http') || combined.contains('api') || combined.contains('fetch')) return Icons.http_rounded;
  if (combined.contains('code') || combined.contains('file') || combined.contains('editor')) return Icons.code_rounded;
  if (combined.contains('docker') || combined.contains('container') || combined.contains('deploy')) return Icons.inventory_2_rounded;
  if (combined.contains('verification') || combined.contains('check') || combined.contains('test')) return Icons.fact_check_rounded;
  return Icons.extension_rounded;
}

String _fieldLabel(String n) => n
    .replaceAll('_', ' ')
    .split(' ')
    .where((w) => w.isNotEmpty)
    .map((w) => '${w[0].toUpperCase()}${w.substring(1)}')
    .join(' ');
String _kindTitle(String k) => switch (k) {
      'trigger' => 'Triggers',
      'retrieval' => 'Code Intelligence',
      'prompt' => 'AI & Prompts',
      'tool' => 'Tools & Actions',
      'approval' => 'Flow Control',
      'verification' => 'Verification',
      'deployment' => 'Deployment',
      'notification' => 'Notifications',
      'memory' => 'Memory & Vector',
      _ => 'Other'
    };
IconData _kindIcon(String k) => switch (k) {
      'trigger' => Icons.bolt_rounded,
      'retrieval' => Icons.search_rounded,
      'prompt' => Icons.psychology_rounded,
      'tool' => Icons.extension_rounded,
      'approval' => Icons.alt_route_rounded,
      'verification' => Icons.checklist_rounded,
      'deployment' => Icons.call_merge_rounded,
      'notification' => Icons.notifications_rounded,
      'memory' => Icons.memory_rounded,
      _ => Icons.widgets_rounded
    };
Color _displayColor(Map<String, dynamic> b) {
  final h = b['display_color']?.toString() ?? '';
  if (h.startsWith('#') && h.length == 7) {
    return Color(int.parse('FF${h.substring(1)}', radix: 16));
  }
  final id = (b['block_id'] ?? b['id'] ?? '').toString().toLowerCase();
  final kind = b['kind']?.toString().toLowerCase() ?? '';

  if (id.contains('condition')) return const Color(0xFFF59E0B);
  if (id.contains('for_each')) return const Color(0xFF10B981);
  if (id.contains('parallel')) return const Color(0xFF3B82F6);
  if (id.contains('subworkflow')) return const Color(0xFF8B5CF6);
  if (id.contains('wait_for_signal')) return const Color(0xFFEC4899);
  if (id.contains('trigger')) return const Color(0xFFEC4899);
  if (id.contains('vector_write')) return const Color(0xFF6366F1);
  if (id.contains('agent')) return const Color(0xFF6366F1);
  if (id.contains('github')) return const Color(0xFF8B5CF6);
  if (id.contains('terminal')) return const Color(0xFF10B981);
  if (id.contains('approval')) return const Color(0xFFF59E0B);
  if (id.contains('prompt') || id.contains('llm')) return const Color(0xFF6366F1);
  if (id.contains('notification')) return const Color(0xFFEC4899);

  return switch (kind) {
    'trigger' => const Color(0xFFEC4899),
    'retrieval' => const Color(0xFF3B82F6),
    'prompt' => const Color(0xFF6366F1),
    'tool' => const Color(0xFF10B981),
    'approval' => const Color(0xFFF59E0B),
    'verification' => const Color(0xFF14B8A6),
    'deployment' => const Color(0xFF8B5CF6),
    'notification' => const Color(0xFFEC4899),
    'memory' => const Color(0xFF6366F1),
    _ => const Color(0xFF64748B),
  };
}

class _NewWorkflowDialog extends StatefulWidget {
  const _NewWorkflowDialog();

  @override
  State<_NewWorkflowDialog> createState() => _NewWorkflowDialogState();
}

class _NewWorkflowDialogState extends State<_NewWorkflowDialog> {
  late final TextEditingController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New Workflow'),
      content: TextField(
        controller: _ctrl,
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Name'),
        textInputAction: TextInputAction.done,
        onSubmitted: (v) => Navigator.pop(context, v),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctrl.text),
          child: const Text('Create'),
        ),
      ],
    );
  }
}

class _RunWorkflowDialog extends StatefulWidget {
  const _RunWorkflowDialog({required this.initialQuery});
  final String initialQuery;

  @override
  State<_RunWorkflowDialog> createState() => _RunWorkflowDialogState();
}

class _RunWorkflowDialogState extends State<_RunWorkflowDialog> {
  late final TextEditingController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: widget.initialQuery);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Run Workflow'),
      content: TextField(
        controller: _ctrl,
        autofocus: true,
        maxLines: 3,
        decoration: const InputDecoration(
          hintText: 'Describe what you want...',
          border: OutlineInputBorder(),
        ),
        textInputAction: TextInputAction.done,
        onSubmitted: (v) => Navigator.pop(context, v),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctrl.text),
          child: const Text('Run'),
        ),
      ],
    );
  }
}

