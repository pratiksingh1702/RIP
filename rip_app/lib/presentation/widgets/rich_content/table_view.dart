import 'package:flutter/material.dart';

class TableView extends StatelessWidget {
  final List<String> headers;
  final List<List<String>> rows;

  const TableView({
    super.key,
    required this.headers,
    required this.rows,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surfaceContainer,
          borderRadius: BorderRadius.circular(8),
        ),
        child: DataTable(
          headingRowColor: WidgetStateProperty.all(
            Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.5),
          ),
          columns: headers.map((header) {
            return DataColumn(
              label: Text(
                header,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            );
          }).toList(),
          rows: rows.map((row) {
            return DataRow(
              cells: row.map((cell) {
                return DataCell(Text(cell));
              }).toList(),
            );
          }).toList(),
        ),
      ),
    );
  }
}
