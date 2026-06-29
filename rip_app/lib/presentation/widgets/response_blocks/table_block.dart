import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../common/section_card.dart';

class TableBlock extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<String> headers;
  final List<List<String>> rows;

  const TableBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.headers,
    required this.rows,
  });

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      icon: Icons.table_chart_rounded,
      iconColor: AppColors.iconDeps,
      title: title,
      subtitle: subtitle,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Container(
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.border),
              borderRadius: BorderRadius.circular(8),
            ),
            child: DataTable(
              headingRowColor: WidgetStateProperty.all(AppColors.surfaceVariant),
              dataRowColor: WidgetStateProperty.all(AppColors.surface),
              horizontalMargin: 12,
              columnSpacing: 24,
              columns: headers.map((header) {
                return DataColumn(
                  label: Text(
                    header,
                    style: AppTextStyles.bodyMdBold.copyWith(color: AppColors.textSecondary),
                  ),
                );
              }).toList(),
              rows: rows.map((row) {
                return DataRow(
                  cells: row.map((cell) {
                    return DataCell(
                      Text(
                        cell,
                        style: AppTextStyles.bodySm.copyWith(color: AppColors.textPrimary),
                      ),
                    );
                  }).toList(),
                );
              }).toList(),
            ),
          ),
        ),
      ),
    );
  }
}
