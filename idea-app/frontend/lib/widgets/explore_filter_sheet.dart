import 'package:flutter/material.dart';

import '../providers/explore_provider.dart';

class ExploreFilterSheet extends StatefulWidget {
  final ExploreFilters initial;
  const ExploreFilterSheet({super.key, required this.initial});

  @override
  State<ExploreFilterSheet> createState() => _ExploreFilterSheetState();
}

class _ExploreFilterSheetState extends State<ExploreFilterSheet> {
  late final TextEditingController _queryController;
  late String _sort;
  late String? _licenseCode;
  late String _allowFork;
  late String? _source;

  @override
  void initState() {
    super.initState();
    _queryController = TextEditingController(text: widget.initial.query ?? '');
    _sort = widget.initial.sort;
    _licenseCode = widget.initial.licenseCode;
    _allowFork = widget.initial.allowFork == null
        ? 'all'
        : (widget.initial.allowFork! ? 'yes' : 'no');
    _source = widget.initial.source;
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  void _apply() {
    Navigator.of(context).pop(
      ExploreFilters(
        query: _queryController.text.trim().isEmpty
            ? null
            : _queryController.text.trim(),
        sort: _sort,
        licenseCode: _licenseCode,
        allowFork: _allowFork == 'all' ? null : _allowFork == 'yes',
        source: _source,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          12,
          20,
          20 + MediaQuery.of(context).viewInsets.bottom,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.outlineVariant,
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Text('探索筛选', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 16),
              TextField(
                controller: _queryController,
                decoration: const InputDecoration(
                  labelText: '关键词',
                  hintText: '搜索公开创意内容',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _sort,
                decoration: const InputDecoration(labelText: '排序方式'),
                items: const [
                  DropdownMenuItem(value: 'recommended', child: Text('智能推荐')),
                  DropdownMenuItem(value: 'latest', child: Text('最新发布')),
                  DropdownMenuItem(value: 'forked', child: Text('衍生最多')),
                ],
                onChanged: (value) => setState(() => _sort = value ?? 'recommended'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String?>(
                value: _licenseCode,
                decoration: const InputDecoration(labelText: '授权类型'),
                items: const [
                  DropdownMenuItem<String?>(value: null, child: Text('全部授权')),
                  DropdownMenuItem(value: 'all_rights_reserved', child: Text('保留所有权利')),
                  DropdownMenuItem(value: 'attribution', child: Text('署名')),
                  DropdownMenuItem(value: 'attribution_adaptation', child: Text('署名-允许改编')),
                  DropdownMenuItem(value: 'custom', child: Text('自定义授权')),
                ],
                onChanged: (value) => setState(() => _licenseCode = value),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _allowFork,
                decoration: const InputDecoration(labelText: '衍生许可'),
                items: const [
                  DropdownMenuItem(value: 'all', child: Text('不限')),
                  DropdownMenuItem(value: 'yes', child: Text('允许衍生')),
                  DropdownMenuItem(value: 'no', child: Text('不允许衍生')),
                ],
                onChanged: (value) => setState(() => _allowFork = value ?? 'all'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String?>(
                value: _source,
                decoration: const InputDecoration(labelText: '创意来源'),
                items: const [
                  DropdownMenuItem<String?>(value: null, child: Text('全部来源')),
                  DropdownMenuItem(value: 'ugc', child: Text('原创')),
                  DropdownMenuItem(value: 'fork', child: Text('Fork')),
                  DropdownMenuItem(value: 'collide', child: Text('Collide')),
                  DropdownMenuItem(value: 'evolve', child: Text('Evolve')),
                ],
                onChanged: (value) => setState(() => _source = value),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => setState(() {
                        _queryController.clear();
                        _sort = 'recommended';
                        _licenseCode = null;
                        _allowFork = 'all';
                        _source = null;
                      }),
                      child: const Text('重置'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: _apply,
                      child: const Text('应用筛选'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
