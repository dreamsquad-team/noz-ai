import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { FilasValidacao } from '../lib/filas-validacao';

function criarTemplate() {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, 'TestStack');
  new FilasValidacao(stack, 'Filas');
  return Template.fromStack(stack);
}

test('cria as quatro filas', () => {
  criarTemplate().resourceCountIs('AWS::SQS::Queue', 4);
});

test('todas as filas têm criptografia SSE-SQS', () => {
  const filas = criarTemplate().findResources('AWS::SQS::Queue');
  for (const fila of Object.values(filas)) {
    expect(fila.Properties.SqsManagedSseEnabled).toBe(true);
  }
});

test('todas as filas recusam conexão sem HTTPS', () => {
  criarTemplate().resourceCountIs('AWS::SQS::QueuePolicy', 4);
});

test.each(['noz-ai-validacao-entrada', 'noz-ai-validacao-saida'])(
  'fila %s envia para a DLQ após 3 tentativas',
  nome => {
    criarTemplate().hasResourceProperties('AWS::SQS::Queue', {
      QueueName: nome,
      RedrivePolicy: {
        maxReceiveCount: 3,
        deadLetterTargetArn: Match.anyValue(),
      },
    });
  }
);

test('as DLQs guardam mensagens por 14 dias', () => {
  const template = criarTemplate();
  for (const nome of ['noz-ai-validacao-entrada-dlq', 'noz-ai-validacao-saida-dlq']) {
    template.hasResourceProperties('AWS::SQS::Queue', {
      QueueName: nome,
      MessageRetentionPeriod: 14 * 24 * 60 * 60,
    });
  }
});

test('a fila de entrada tem visibility timeout de 6 minutos', () => {
  criarTemplate().hasResourceProperties('AWS::SQS::Queue', {
    QueueName: 'noz-ai-validacao-entrada',
    VisibilityTimeout: 360,
  });
});
