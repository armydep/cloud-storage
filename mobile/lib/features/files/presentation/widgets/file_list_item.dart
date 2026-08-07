import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/material.dart';

class FileListItem extends StatelessWidget {
  final FileContent item;
  final VoidCallback? onTap;
  final VoidCallback? onDownload;
  final VoidCallback? onCancel;
  final double? downloadProgress;
  final String? downloadError;

  const FileListItem({
    required this.item,
    this.onTap,
    this.onDownload,
    this.onCancel,
    this.downloadProgress,
    this.downloadError,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        ListTile(
          key: Key('file-item-${item.id}'),
          leading: item.isFolder
              ? const Icon(Icons.folder_outlined, color: Colors.blue)
              : _getCategoryIcon(),
          title: Text(item.name),
          subtitle: _buildSubtitle(),
          onTap: onTap,
          trailing: _buildTrailing(context),
        ),
        if (downloadProgress != null && downloadProgress! > 0)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: LinearProgressIndicator(value: downloadProgress),
          ),
      ],
    );
  }

  Widget _buildSubtitle() {
    if (downloadError != null) {
      return Text(
        downloadError!,
        style: const TextStyle(color: Colors.red, fontSize: 12),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      );
    }
    if (downloadProgress != null && downloadProgress! > 0) {
      return Text('${(downloadProgress! * 100).toStringAsFixed(0)}%');
    }
    if (item.isFile) {
      return Text(item.displaySize);
    }
    return null;
  }

  Widget? _buildTrailing(BuildContext context) {
    if (item.isFolder) {
      return const Icon(Icons.chevron_right);
    }
    if (downloadProgress != null && downloadProgress! > 0 && downloadProgress! < 1.0) {
      return IconButton(
        icon: const Icon(Icons.close),
        onPressed: onCancel,
        tooltip: 'Cancel download',
      );
    }
    if (downloadError != null) {
      return IconButton(
        icon: const Icon(Icons.refresh, color: Colors.red),
        onPressed: onDownload,
        tooltip: 'Retry download',
      );
    }
    return IconButton(
      icon: const Icon(Icons.download),
      onPressed: onDownload,
      tooltip: 'Download file',
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
