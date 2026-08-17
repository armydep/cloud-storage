import 'package:cloudestorage/features/files/application/files_providers.dart';
import 'package:cloudestorage/features/files/domain/file_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

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
  void initState() {
    super.initState();
    Future.microtask(() => _loadShares());
  }

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  void _loadShares() {
    ref.read(filesControllerProvider.notifier).loadFileShares(widget.fileId);
  }

  void _revoke(String shareId) {
    ref
        .read(filesControllerProvider.notifier)
        .revokeFileShare(fileId: widget.fileId, shareId: shareId);
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
      content: SingleChildScrollView(
        child: Form(
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
              const SizedBox(height: 20),
              Text(
                'People with access',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              _RecipientsList(fileId: widget.fileId, onRevoke: _revoke),
            ],
          ),
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

/// The "People with access" section of [ShareFileDialog]: loading, error
/// with retry, empty state, or the current recipient list.
class _RecipientsList extends ConsumerWidget {
  final String fileId;
  final void Function(String shareId) onRevoke;

  const _RecipientsList({required this.fileId, required this.onRevoke});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isLoading = ref.watch(
      filesControllerProvider.select((state) => state.isLoadingShares),
    );
    final error = ref.watch(
      filesControllerProvider.select((state) => state.sharesError),
    );
    final shares = ref.watch(
      filesControllerProvider.select((state) => state.shares),
    );

    if (isLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: SizedBox(
          key: Key('share-recipients-loading'),
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    if (error != null) {
      return Row(
        children: [
          Expanded(
            child: Text(
              error,
              key: const Key('share-recipients-error'),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
          TextButton(
            key: const Key('share-recipients-retry-button'),
            onPressed: () => ref
                .read(filesControllerProvider.notifier)
                .loadFileShares(fileId),
            child: const Text('Retry'),
          ),
        ],
      );
    }

    if (shares.isEmpty) {
      return const Text('This file is not shared with anyone yet.');
    }

    // The dialog's content is already scrollable (see `ShareFileDialog`), so
    // this is a plain Column rather than a nested `ListView` -- a shrink-wrapped
    // list inside a dialog's intrinsic-height layout throws
    // "RenderShrinkWrappingViewport does not support returning intrinsic
    // dimensions". Recipient counts are small enough that this doesn't need
    // its own scroll region.
    return Column(
      children: [
        for (final share in shares)
          _RecipientRow(share: share, onRevoke: onRevoke),
      ],
    );
  }
}

class _RecipientRow extends ConsumerWidget {
  final FileShare share;
  final void Function(String shareId) onRevoke;

  const _RecipientRow({required this.share, required this.onRevoke});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isRevoking = ref.watch(
      filesControllerProvider.select(
        (state) => state.isRevokingShare(share.id),
      ),
    );
    final revokeError = ref.watch(
      filesControllerProvider.select(
        (state) => state.getRevokeShareError(share.id),
      ),
    );

    return Padding(
      key: Key('share-recipient-row-${share.id}'),
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(share.recipientEmail),
                    Text(
                      'Shared ${DateFormat.yMMMd().format(share.createdAt.toLocal())}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              isRevoking
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : IconButton(
                      key: Key('revoke-share-button-${share.id}'),
                      tooltip: 'Revoke access for ${share.recipientEmail}',
                      icon: const Icon(Icons.remove_circle_outline),
                      onPressed: () => onRevoke(share.id),
                    ),
            ],
          ),
          if (revokeError != null)
            Text(
              revokeError,
              key: Key('revoke-share-error-${share.id}'),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ],
      ),
    );
  }
}
