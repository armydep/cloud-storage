import 'dart:async';

import 'package:cloudestorage/features/auth/data/token_storage.dart';

class AuthSession {
  AuthSession(this._storage);

  final TokenStorage _storage;
  final StreamController<void> _invalidations = StreamController.broadcast();
  Future<void> _pendingOperation = Future.value();

  Stream<void> get invalidations => _invalidations.stream;
  Future<String?> readToken() => _locked(_storage.read);

  Future<void> saveToken(String token) => _locked(() => _storage.write(token));

  Future<void> clear() {
    return _locked(() async {
      await _storage.delete();
      _invalidations.add(null);
    });
  }

  Future<bool> clearIfMatches(String token) {
    return _locked(() async {
      if (await _storage.read() != token) return false;
      await _storage.delete();
      _invalidations.add(null);
      return true;
    });
  }

  Future<T> _locked<T>(Future<T> Function() operation) {
    final result = _pendingOperation.then((_) => operation());
    _pendingOperation = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  Future<void> dispose() => _invalidations.close();
}
