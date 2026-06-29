import 'package:flutter/material.dart';
import '../../../core/design/app_colors.dart';
import '../../../core/design/app_text_styles.dart';
import '../common/section_card.dart';

class FileListBlock extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<String> files;

  const FileListBlock({
    super.key,
    required this.title,
    this.subtitle,
    required this.files,
  });

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      icon: Icons.insert_drive_file_rounded,
      iconColor: AppColors.iconFiles,
      title: title,
      subtitle: subtitle,
      child: Column(
        children: files.map((file) {
          final parts = file.split('/');
          final filename = parts.last;
          final directory = parts.length > 1 ? parts.sublist(0, parts.length - 1).join('/') : '';

          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: ListTile(
              dense: true,
              leading: const Icon(
                Icons.description_outlined,
                color: AppColors.iconFiles,
                size: 20,
              ),
              title: Text(
                filename,
                style: AppTextStyles.bodyMdBold,
              ),
              subtitle: directory.isNotEmpty
                ? Text(
                    directory,
                    style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  )
                : null,
              onTap: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Opening file: $file')),
                );
              },
            ),
          );
        }).toList(),
      ),
    );
  }
}
