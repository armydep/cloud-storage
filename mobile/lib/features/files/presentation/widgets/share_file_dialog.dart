import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// A dialog that lets the owner of [fileId] grant another registered user
/// download access to it.
///
/// Self-contained: it reads and drives `filesControllerProvider` directly, so
/// callers just need `showDialog(context: context, builder: (_) =>
/// ShareFileDialog(fileId: ..., fileName: ...))`. It shares `FilesState`
/// with the rest of the file browser, matching how create-folder and delete
/// already track their transient UI state on the same controller.
class ShareFileDialog extends ConsumerStatefulWidget {
  final String fileId;
  final String fileName;

  const ShareFileDialog({
    super.key,
    required this.fileId,
    required this.fileName,
  });

  @override
  ConsumerState<ShareFileDialog> createState() => _ShareFileDialogState();
}

class _ShareFileDialogState extends ConsumerState<ShareFileDialog> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  String? _validateEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty || !email.contains('@')) {
      return 'Enter a valid email address.';
    }
    return null;
  }

  void _submit() {
    if (_formKey.currentState?.validate() != true) return;
    ref
        .read(filesControllerProvider.notifier)
        .shareFile(
          fileId: widget.fileId,
          recipientEmail: _emailController.text.trim(),
        );
  }

  @override
  Widget build(BuildContext context) {
    final isSharing = ref.watch(
      filesControllerProvider.select((state) => state.isSharing),
    );
    final shareError = ref.watch(
      filesControllerProvider.select((state) => state.shareError),
    );

    ref.listen(filesControllerProvider, (previous, next) {
      final justFinished = previous?.isSharing == true && !next.isSharing;
      if (justFinished && next.shareError == null) {
        if (Navigator.canPop(context)) Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('File shared successfully')),
        );
      }
    });

    return AlertDialog(
      title: const Text('Share file'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Give another user download access to ${widget.fileName}.'),
            const SizedBox(height: 16),
            TextFormField(
              key: const Key('share-recipient-email-field'),
              controller: _emailController,
              enabled: !isSharing,
              autofocus: true,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.done,
              onFieldSubmitted: (_) => _submit(),
              decoration: const InputDecoration(
                labelText: 'Recipient email',
                hintText: 'user@example.com',
                border: OutlineInputBorder(),
              ),
              validator: _validateEmail,
            ),
            if (shareError != null) ...[
              const SizedBox(height: 12),
              Text(
                shareError,
                key: const Key('share-error-text'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: isSharing ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          key: const Key('share-submit-button'),
          onPressed: isSharing ? null : _submit,
          child: isSharing
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Share'),
        ),
      ],
    );
  }
}
