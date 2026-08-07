import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/material.dart';

class FileListItem extends StatelessWidget {
  final FileContent item;
  final VoidCallback? onTap;

  const FileListItem({
    required this.item,
    this.onTap,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: Key('file-item-${item.id}'),
      leading: item.isFolder
          ? const Icon(Icons.folder_outlined, color: Colors.blue)
          : _getCategoryIcon(),
      title: Text(item.name),
      subtitle: item.isFile ? Text(item.displaySize) : null,
      onTap: onTap,
      trailing: item.isFolder ? const Icon(Icons.chevron_right) : null,
    );
  }

  Widget _getCategoryIcon() {
    final category = item.category?.toLowerCase() ?? 'document';

    switch (category) {
      case 'image':
        return const Icon(Icons.image, color: Colors.purple);
      case 'video':
        return const Icon(Icons.videocam, color: Colors.red);
      case 'audio':
        return const Icon(Icons.audio_file, color: Colors.orange);
      case 'document':
        return const Icon(Icons.description, color: Colors.blue);
      case 'archive':
        return const Icon(Icons.folder_zip, color: Colors.brown);
      default:
        return const Icon(Icons.insert_drive_file, color: Colors.grey);
    }
  }
}
