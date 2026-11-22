import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

/// Public creator discovery, ranked by publicly visible work only.
class CreatorsScreen extends ConsumerStatefulWidget {
  const CreatorsScreen({super.key});

  @override
  ConsumerState<CreatorsScreen> createState() => _CreatorsScreenState();
}

class _CreatorsScreenState extends ConsumerState<CreatorsScreen> {
  final _queryController = TextEditingController();
  List<Map<String, dynamic>> _items = [];
  bool _loading = false;
  bool _searched = false;
  String? _error;

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _queryController.text.trim();
    if (query.length < 2) {
      setState(() => _error = '请输入至少 2 个字符');
      return;
    }
    setState(() {
      _loading = true;
      _searched = true;
      _error = null;
    });
    try {
      final items = await ref.read(userServiceProvider).searchPublicCreators(query);
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('发现创作者')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _queryController,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                labelText: '搜索创作者',
                hintText: '输入用户名关键词',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(
                  tooltip: '搜索',
                  onPressed: _loading ? null : _search,
                  icon: const Icon(Icons.arrow_forward),
                ),
              ),
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          Expanded(
            child: !_searched
                ? const Center(child: Text('搜索公开创作者，发现他们的创意和贡献'))
                : _items.isEmpty && !_loading
                    ? const Center(child: Text('没有找到匹配的公开创作者'))
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: _items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          final id = item['id'] as String;
                          return Card(
                            child: ListTile(
                              leading: const CircleAvatar(
                                child: Icon(Icons.person_outline),
                              ),
                              title: Text(item['username'] as String? ?? '创作者'),
                              subtitle: Text(
                                '公开创意 ${item['public_idea_count'] ?? 0} · '
                                '公开贡献 ${item['public_contribution_count'] ?? 0}'
                                '${(item['bio'] as String? ?? '').isEmpty ? '' : '\n${item['bio']}'}',
                              ),
                              isThreeLine: (item['bio'] as String? ?? '').isNotEmpty,
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () => context.push('/user/$id'),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
