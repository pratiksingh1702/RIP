import 'package:flutter/material.dart';
import '../../../../domain/enums/job_status.dart';

class StatusBadge extends StatelessWidget {
  final JobStatus status;

  const StatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color color;
    String text;

    switch (status) {
      case JobStatus.pending:
        color = Colors.grey;
        text = 'Pending';
        break;
      case JobStatus.cloning:
        color = Colors.blue;
        text = 'Cloning';
        break;
      case JobStatus.indexing:
        color = Colors.orange;
        text = 'Indexing';
        break;
      case JobStatus.complete:
        color = Colors.green;
        text = 'Complete';
        break;
      case JobStatus.failed:
        color = Colors.red;
        text = 'Failed';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
