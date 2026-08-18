import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/material.dart';

class FileListItem extends StatelessWidget {
  final FileContent item;
  final VoidCallback? onTap;
  final VoidCallback? onDownload;
  final VoidCallback? onCancel;
  final VoidCallback? onOpen;
  final VoidCallback? onDelete;
  final double? downloadProgress;
  final String? downloadError;
  final double? uploadProgress;
  final String? uploadError;
  final bool isDeleting;
  // Set only by search results, which can come from any subfolder of the
  // searched one (design doc decision 11): without this, two same-named
  // files in different subfolders are indistinguishable. The folder browser
  // never passes it, since every row there is already known to be in the
  // folder being viewed.
  final String? folderPathCaption;

  const FileListItem({
    required this.item,
    this.onTap,
    this.onDownload,
    this.onCancel,
    this.onOpen,
    this.onDelete,
    this.downloadProgress,
    this.downloadError,
    this.uploadProgress,
    this.uploadError,
    this.isDeleting = false,
    this.folderPathCaption,
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
          subtitle: _buildSubtitleWithCaption(),
          onTap: onTap,
          trailing: _buildTrailing(),
        ),
        if (downloadProgress != null && downloadProgress! > 0)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: LinearProgressIndicator(value: downloadProgress),
          ),
        if (uploadProgress != null && uploadProgress! > 0)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: LinearProgressIndicator(value: uploadProgress),
          ),
      ],
    );
  }

  Widget? _buildSubtitleWithCaption() {
    final subtitle = _buildSubtitle();
    if (folderPathCaption == null) return subtitle;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        ?subtitle,
        Text(
          folderPathCaption!,
          style: const TextStyle(fontSize: 11, color: Colors.grey),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  Widget? _buildSubtitle() {
    if (uploadError != null) {
      return Text(
        uploadError!,
        style: const TextStyle(color: Colors.red, fontSize: 12),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      );
    }
    if (uploadProgress != null && uploadProgress! > 0) {
      return Text('Uploading ${(uploadProgress! * 100).toStringAsFixed(0)}%');
    }
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

  Widget? _buildTrailing() {
    if (isDeleting) {
      return const SizedBox(
        width: 24,
        height: 24,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    if (item.isFolder) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            key: Key('delete-folder-${item.id}'),
            icon: const Icon(Icons.delete_outline, color: Colors.red),
            onPressed: onDelete,
            tooltip: 'Delete folder',
          ),
          const Icon(Icons.chevron_right),
        ],
      );
    }

    final primaryAction = _buildPrimaryFileAction();
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (primaryAction != null) ...[primaryAction],
        IconButton(
          key: Key('delete-file-${item.id}'),
          icon: const Icon(Icons.delete_outline, color: Colors.red),
          onPressed: onDelete,
          tooltip: 'Delete file',
        ),
      ],
    );
  }

  Widget? _buildPrimaryFileAction() {
    if (downloadProgress != null && downloadProgress! >= 1.0) {
      return IconButton(
        icon: const Icon(Icons.open_in_new),
        onPressed: onOpen,
        tooltip: 'Open file',
      );
    }
    if (downloadProgress != null &&
        downloadProgress! > 0 &&
        downloadProgress! < 1.0) {
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
