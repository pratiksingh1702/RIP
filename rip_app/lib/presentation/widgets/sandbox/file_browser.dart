import 'package:flutter/material.dart';
class SandboxFileBrowser extends StatelessWidget {
  final List<Map<String, dynamic>> files;
  final Function(String path) onFileTap;
  const SandboxFileBrowser({super.key, required this.files, required this.onFileTap});
  @override
  Widget build(BuildContext context) => ListView.builder(
    itemCount: files.length,
    itemBuilder: (context, index) {
      final file = files[index];
      return ListTile(
        leading: Icon(file['is_directory'] == true ? Icons.folder : Icons.insert_drive_file, color: file['is_directory'] == true ? Colors.amber : Colors.white54, size: 20),
        title: Text(file['name'] ?? '', style: const TextStyle(color: Colors.white, fontSize: 13)),
        subtitle: Text(file['path'] ?? '', style: const TextStyle(color: Colors.white38, fontSize: 11)),
        dense: true,
        onTap: () => onFileTap(file['path'] ?? ''),
      );
    },
  );
}
