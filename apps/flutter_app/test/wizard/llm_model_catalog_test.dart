import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/wizard/llm_model_catalog.dart';
import 'package:flutter_app/wizard/llm_provider.dart';

void main() {
  group('CatalogModel', () {
    test('has id, name, and optional metadata', () {
      const model = CatalogModel(
        id: 'test-model',
        name: 'Test Model',
        contextWindow: 128000,
        maxTokens: 4096,
        reasoning: true,
      );
      expect(model.id, 'test-model');
      expect(model.name, 'Test Model');
      expect(model.contextWindow, 128000);
      expect(model.maxTokens, 4096);
      expect(model.reasoning, isTrue);
      expect(model.inputModalities, ['text']);
    });

    test('defaults reasoning to false', () {
      const model = CatalogModel(id: 'x', name: 'X');
      expect(model.reasoning, isFalse);
    });
  });

  group('LlmModelCatalog', () {
    test('deepseek catalog has 2 models', () {
      expect(LlmModelCatalog.deepseek.length, 2);
      expect(LlmModelCatalog.deepseek[0].id, 'deepseek-v4-flash');
      expect(LlmModelCatalog.deepseek[1].id, 'deepseek-v4-pro');
    });

    test('openai catalog has models', () {
      expect(LlmModelCatalog.openai.length, greaterThan(0));
      expect(
        LlmModelCatalog.openai.any((m) => m.id == 'gpt-4o'),
        isTrue,
      );
    });

    test('anthropic catalog has Claude models', () {
      expect(LlmModelCatalog.anthropic.length, greaterThan(0));
      expect(
        LlmModelCatalog.anthropic.any((m) => m.id == 'claude-sonnet-4-5'),
        isTrue,
      );
    });

    test('google catalog has Gemini models', () {
      expect(LlmModelCatalog.google.length, greaterThan(0));
      expect(
        LlmModelCatalog.google.any((m) => m.id == 'gemini-2.5-flash'),
        isTrue,
      );
    });

    test('forProvider returns catalog for known providers', () {
      expect(LlmModelCatalog.forProvider('deepseek').length, 2);
      expect(LlmModelCatalog.forProvider('openai').length, greaterThan(0));
      expect(LlmModelCatalog.forProvider('anthropic').length, greaterThan(0));
    });

    test('forProvider returns empty for unknown/custom', () {
      expect(LlmModelCatalog.forProvider('custom'), isEmpty);
      expect(LlmModelCatalog.forProvider('unknown'), isEmpty);
    });

    test('findModel returns model when found', () {
      final model = LlmModelCatalog.findModel('deepseek', 'deepseek-v4-flash');
      expect(model, isNotNull);
      expect(model!.name, 'DeepSeek V4 Flash');
      expect(model.contextWindow, 1000000);
    });

    test('findModel returns null when not found', () {
      expect(LlmModelCatalog.findModel('deepseek', 'nonexistent'), isNull);
    });

    test('all deepseek models have 1M context window', () {
      for (final m in LlmModelCatalog.deepseek) {
        expect(m.contextWindow, 1000000,
            reason: '${m.id} should have 1M context');
      }
    });

    test('all deepseek models support reasoning', () {
      for (final m in LlmModelCatalog.deepseek) {
        expect(m.reasoning, isTrue,
            reason: '${m.id} should support reasoning');
      }
    });
  });

  group('LlmProvider model catalog integration', () {
    test('deepseek provider has model catalog', () {
      expect(LlmProvider.deepseek.models.length, 2);
      expect(LlmProvider.deepseek.models.first.id, 'deepseek-v4-flash');
    });

    test('openai provider has model catalog', () {
      expect(LlmProvider.openai.models.length, greaterThan(0));
    });

    test('custom provider has empty catalog', () {
      expect(LlmProvider.custom.models, isEmpty);
    });

    test('findModel on provider finds catalog model', () {
      final model = LlmProvider.deepseek.findModel('deepseek-v4-pro');
      expect(model, isNotNull);
      expect(model!.name, 'DeepSeek V4 Pro');
    });

    test('findModel on provider returns null for unlisted', () {
      expect(LlmProvider.deepseek.findModel('custom-model'), isNull);
    });

    test('all providers have correct api protocol', () {
      expect(LlmProvider.deepseek.apiProtocol.wire, 'openai-completions');
      expect(LlmProvider.openai.apiProtocol.wire, 'openai-responses');
      expect(LlmProvider.anthropic.apiProtocol.wire, 'anthropic-messages');
      expect(LlmProvider.google.apiProtocol.wire, 'google-generative-ai');
    });
  });

  group('LlmProvider expanded provider list', () {
    test('all has 9 providers', () {
      expect(LlmProvider.all.length, 9);
    });

    test('all provider ids are unique', () {
      final ids = LlmProvider.all.map((p) => p.id).toList();
      expect(ids.toSet().length, ids.length);
    });

    test('byId finds all providers', () {
      for (final p in LlmProvider.all) {
        expect(LlmProvider.byId(p.id).id, p.id);
      }
    });

    test('byId returns deepseek for unknown', () {
      expect(LlmProvider.byId('nonexistent').id, 'deepseek');
    });

    test('anthropic has multiple env vars', () {
      expect(LlmProvider.anthropic.apiKeyEnvVars.length, 2);
      expect(LlmProvider.anthropic.apiKeyEnvVars,
          contains('ANTHROPIC_API_KEY'));
      expect(LlmProvider.anthropic.apiKeyEnvVars,
          contains('ANTHROPIC_AUTH_TOKEN'));
    });

    test('google uses GEMINI_API_KEY', () {
      expect(LlmProvider.google.apiKeyEnvVar, 'GEMINI_API_KEY');
    });

    test('qwen uses QWEN_TOKEN_PLAN_API_KEY', () {
      expect(LlmProvider.qwen.apiKeyEnvVar, 'QWEN_TOKEN_PLAN_API_KEY');
    });
  });
}
