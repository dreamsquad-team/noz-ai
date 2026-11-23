import { Duration } from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';

export interface FilasValidacaoProps {
  /** Tempo que a mensagem fica invisível enquanto é processada. Deve ser maior que o timeout da Lambda. */
  visibilityTimeout?: Duration;
  /** Quantas vezes a mensagem é entregue antes de ir para a DLQ. */
  maxReceiveCount?: number;
}

export class FilasValidacao extends Construct {
  public readonly entrada: sqs.Queue;
  public readonly entradaDlq: sqs.Queue;
  public readonly saida: sqs.Queue;
  public readonly saidaDlq: sqs.Queue;

  constructor(scope: Construct, id: string, props: FilasValidacaoProps = {}) {
    super(scope, id);

    // TODO: valores provisórios, confirmar com o líder
    const maxReceiveCount = props.maxReceiveCount ?? 3;
    const visibilityTimeout = props.visibilityTimeout ?? Duration.minutes(6);

    const comum = {
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      enforceSSL: true,
    };

    this.entradaDlq = new sqs.Queue(this, 'EntradaDlq', {
      ...comum,
      queueName: 'noz-ai-validacao-entrada-dlq',
      retentionPeriod: Duration.days(14),
    });

    this.saidaDlq = new sqs.Queue(this, 'SaidaDlq', {
      ...comum,
      queueName: 'noz-ai-validacao-saida-dlq',
      retentionPeriod: Duration.days(14),
    });

    this.entrada = new sqs.Queue(this, 'Entrada', {
      ...comum,
      queueName: 'noz-ai-validacao-entrada',
      visibilityTimeout,
      deadLetterQueue: { queue: this.entradaDlq, maxReceiveCount },
    });

    this.saida = new sqs.Queue(this, 'Saida', {
      ...comum,
      queueName: 'noz-ai-validacao-saida',
      deadLetterQueue: { queue: this.saidaDlq, maxReceiveCount },
    });
  }
}
