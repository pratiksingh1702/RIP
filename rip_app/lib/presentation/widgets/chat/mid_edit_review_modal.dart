import 'package:flutter/material.dart';
import 'package:rip_app/data/models/supervisor_event.dart';

class MidEditReviewModal extends StatelessWidget {
  final FilePlanItem filePlan;
  final VoidCallback onApprove;
  final ValueChanged<String> onModify;
  final VoidCallback onReject;

  const MidEditReviewModal({
    super.key,
    required this.filePlan,
    required this.onApprove,
    required this.onModify,
    required this.onReject,
  });

  static void show(
    BuildContext context, {
    required FilePlanItem filePlan,
    required VoidCallback onApprove,
    required ValueChanged<String> onModify,
    required VoidCallback onReject,
  }) {
    showDialog(
      context: context,
      builder: (context) => MidEditReviewModal(
        filePlan: filePlan,
        onApprove: onApprove,
        onModify: onModify,
        onReject: onReject,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final TextEditingController modController = TextEditingController();

    return AlertDialog(
      backgroundColor: const Color(0xFF18181B),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Colors.white12),
      ),
      title: Row(
        children: [
          Icon(
            filePlan.hasHighFanIn ? Icons.warning_amber_rounded : Icons.code,
            color: filePlan.hasHighFanIn ? Colors.amberAccent : Colors.cyanAccent,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Planned Edit: ${filePlan.filePath}',
              style: const TextStyle(color: Colors.white, fontSize: 16),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (filePlan.hasHighFanIn)
              Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.amber.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.amber.withOpacity(0.4)),
                ),
                child: Text(
                  'High Blast Radius: Touches ${filePlan.dependentCount} dependent modules.',
                  style: const TextStyle(color: Colors.amberAccent, fontSize: 12),
                ),
              ),
            Text(
              'Rationale: ${filePlan.rationale}',
              style: const TextStyle(color: Colors.white70, fontSize: 13),
            ),
            const SizedBox(height: 12),
            const Text(
              'Proposed Diff Preview:',
              style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white10),
              ),
              child: SelectableText(
                filePlan.proposedDiff.isEmpty ? '// No diff preview available' : filePlan.proposedDiff,
                style: const TextStyle(fontFamily: 'monospace', color: Colors.greenAccent, fontSize: 12),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: modController,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              decoration: const InputDecoration(
                hintText: 'Optional instructions to modify this step...',
                hintStyle: TextStyle(color: Colors.white38),
                filled: true,
                fillColor: Color(0xFF22242B),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () {
            Navigator.pop(context);
            onReject();
          },
          child: const Text('Reject Step', style: TextStyle(color: Colors.redAccent)),
        ),
        TextButton(
          onPressed: () {
            Navigator.pop(context);
            onModify(modController.text.trim());
          },
          child: const Text('Modify Plan', style: TextStyle(color: Colors.orangeAccent)),
        ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent),
          onPressed: () {
            Navigator.pop(context);
            onApprove();
          },
          child: const Text('Approve', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
        ),
      ],
    );
  }
}
