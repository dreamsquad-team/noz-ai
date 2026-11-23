import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface BucketEvidenciasProps {
  /** Dias até a AWS apagar automaticamente cada evidência. */
  diasParaExpirar?: number;
}

export class BucketEvidencias extends Construct {
  public readonly bucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: BucketEvidenciasProps = {}) {
    super(scope, id);

    // TODO: valor provisório, confirmar com o líder e a NOZ (LGPD)
    const diasParaExpirar = props.diasParaExpirar ?? 90;

    this.bucket = new s3.Bucket(this, 'Bucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          expiration: Duration.days(diasParaExpirar),
          abortIncompleteMultipartUploadAfter: Duration.days(7),
        },
      ],
    });
  }
}
