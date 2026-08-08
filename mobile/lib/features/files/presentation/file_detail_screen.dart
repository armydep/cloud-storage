import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class FileDetailScreen extends StatelessWidget {
  final FileContent file;

  const FileDetailScreen({
    super.key,
    required this.file,
  });

  String _formatDateTime(DateTime dateTime) {
    return DateFormat('MMM d, yyyy \'at\' h:mm a').format(dateTime);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('File Details'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _DetailSection(
              title: 'File Name',
              value: file.name,
            ),
            const SizedBox(height: 24),
            _DetailSection(
              title: 'Size',
              value: file.displaySize.isNotEmpty ? file.displaySize : 'Unknown',
            ),
            const SizedBox(height: 24),
            _DetailSection(
              title: 'Created',
              value: file.createdAt != null
                  ? _formatDateTime(file.createdAt!)
                  : 'Unknown',
            ),
            const SizedBox(height: 24),
            _DetailSection(
              title: 'MIME Type',
              value: file.mimeType ?? 'Unknown',
            ),
            const SizedBox(height: 24),
            _DetailSection(
              title: 'Owner',
              value: file.ownerEmail ?? 'Unknown',
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailSection extends StatelessWidget {
  final String title;
  final String value;

  const _DetailSection({
    required this.title,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: Colors.grey[600],
              ),
        ),
        const SizedBox(height: 8),
        SelectableText(
          value,
          style: Theme.of(context).textTheme.bodyLarge,
        ),
      ],
    );
  }
}
