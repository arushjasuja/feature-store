from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, window, avg, stddev, max as spark_max, min as spark_min,
    from_json, to_timestamp, current_timestamp, unix_timestamp
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
import logging

logger = logging.getLogger(__name__)


class FeatureProcessor:
    """
    Spark Structured Streaming processor for real-time feature computation.
    Consumes events from Kafka, computes windowed aggregations,
    and writes to PostgreSQL and Redis.
    """
    
    def __init__(self, kafka_brokers: str, postgres_url: str, redis_url: str):
        self.kafka_brokers = kafka_brokers
        self.postgres_url = postgres_url
        self.redis_url = redis_url
        self.spark = None
    
    def initialize_spark(self):
        """Initialize Spark session with required configurations"""
        self.spark = SparkSession.builder \
            .appName("FeatureStore_Streaming") \
            .config("spark.jars.packages",
                   "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,"
                   "org.postgresql:postgresql:42.6.0") \
            .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoints") \
            .config("spark.sql.shuffle.partitions", "10") \
            .config("spark.streaming.kafka.maxRatePerPartition", "1000") \
            .getOrCreate()
        
        # Set log level
        self.spark.sparkContext.setLogLevel("WARN")
        logger.info("Spark session initialized")
    
    def create_event_schema(self) -> StructType:
        """Define schema for incoming Kafka events"""
        return StructType([
            StructField("entity_id", StringType(), False),
            StructField("event_type", StringType(), False),
            StructField("value", DoubleType(), False),
            StructField("timestamp", StringType(), False),
            StructField("metadata", StringType(), True)
        ])
    
    def process_stream(self, topic: str = "feature_events"):
        """
        Main stream processing pipeline.
        
        Pipeline:
        1. Read from Kafka
        2. Parse JSON events
        3. Compute windowed aggregations
        4. Write to PostgreSQL and Redis
        
        Args:
            topic: Kafka topic to consume from
        """
        if not self.spark:
            self.initialize_spark()
        
        schema = self.create_event_schema()
        
        # Read from Kafka
        logger.info(f"Starting to consume from Kafka topic: {topic}")
        df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", self.kafka_brokers) \
            .option("subscribe", topic) \
            .option("startingOffsets", "latest") \
            .option("maxOffsetsPerTrigger", "10000") \
            .option("failOnDataLoss", "false") \
            .load()
        
        # Parse JSON and extract timestamp
        parsed = df.select(
            from_json(col("value").cast("string"), schema).alias("data")
        ).select("data.*") \
         .withColumn("timestamp", to_timestamp("timestamp")) \
         .withColumn("processing_time", current_timestamp())
        
        # Compute multiple windowed aggregations
        # 5-minute windows with 1-minute slides
        windowed = parsed \
            .withWatermark("timestamp", "10 minutes") \
            .groupBy(
                "entity_id",
                "event_type",
                window("timestamp", "5 minutes", "1 minute")
            ) \
            .agg(
                avg("value").alias("avg_5min"),
                stddev("value").alias("stddev_5min"),
                spark_max("value").alias("max_5min"),
                spark_min("value").alias("min_5min"),
                spark_max("processing_time").alias("last_updated")
            ) \
            .select(
                col("entity_id"),
                col("event_type"),
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("avg_5min"),
                col("stddev_5min"),
                col("max_5min"),
                col("min_5min"),
                col("last_updated")
            )
        
        # Write stream with custom batch processing
        query = windowed.writeStream \
            .foreachBatch(self._write_batch) \
            .outputMode("update") \
            .trigger(processingTime="10 seconds") \
            .start()
        
        logger.info("Stream processing started")
        query.awaitTermination()
    
    def _write_batch(self, batch_df, batch_id: int):
        """
        Write each micro-batch to PostgreSQL and Redis.
        
        Args:
            batch_df: Spark DataFrame for this batch
            batch_id: Batch identifier
        """
        if batch_df.isEmpty():
            logger.debug(f"Batch {batch_id} is empty, skipping")
            return
        
        logger.info(f"Processing batch {batch_id} with {batch_df.count()} records")
        
        # Write to PostgreSQL
        try:
            self._write_to_postgres(batch_df, batch_id)
        except Exception as e:
            logger.error(f"Failed to write batch {batch_id} to PostgreSQL: {e}")
        
        # Write to Redis cache
        try:
            self._write_to_redis(batch_df, batch_id)
        except Exception as e:
            logger.error(f"Failed to write batch {batch_id} to Redis: {e}")
    
    def _write_to_postgres(self, batch_df, batch_id: int):
        """
        Write batch to PostgreSQL using JDBC.
        
        Note: In production, consider using COPY protocol for better performance.
        """
        # Transform to feature_values table format
        # This is a simplified version - in production, you'd join with features table
        # to get feature_ids
        
        batch_df.write \
            .format("jdbc") \
            .option("url", self.postgres_url) \
            .option("dbtable", "feature_values_staging") \
            .option("driver", "org.postgresql.Driver") \
            .option("batchsize", "1000") \
            .mode("append") \
            .save()
        
        logger.info(f"Batch {batch_id} written to PostgreSQL")
    
    def _write_to_redis(self, batch_df, batch_id: int):
        """
        Write recent features to Redis cache for fast lookups.
        Uses foreachPartition for efficient batch writes.
        """
        def write_partition_to_redis(partition):
            """Write each partition to Redis"""
            import redis
            import msgpack
            from datetime import datetime
            
            try:
                r = redis.from_url(self.redis_url)
                pipe = r.pipeline()
                count = 0
                
                for row in partition:
                    # Create cache keys for each feature
                    features = {
                        f"{row.entity_id}:avg_5min_{row.event_type}": {
                            'value': float(row.avg_5min) if row.avg_5min else None,
                            'timestamp': row.window_end.isoformat(),
                            'freshness_seconds': 0
                        },
                        f"{row.entity_id}:max_5min_{row.event_type}": {
                            'value': float(row.max_5min) if row.max_5min else None,
                            'timestamp': row.window_end.isoformat(),
                            'freshness_seconds': 0
                        }
                    }
                    
                    # Write to Redis with 1-hour TTL
                    for key, value in features.items():
                        if value['value'] is not None:
                            pipe.setex(key, 3600, msgpack.packb(value, use_bin_type=True))
                            count += 1
                
                pipe.execute()
                logger.debug(f"Wrote {count} features to Redis from partition")
                
            except Exception as e:
                logger.error(f"Failed to write partition to Redis: {e}")
        
        # Process each partition
        batch_df.foreachPartition(write_partition_to_redis)
        logger.info(f"Batch {batch_id} written to Redis")
    
    def stop(self):
        """Stop Spark session"""
        if self.spark:
            self.spark.stop()
            logger.info("Spark session stopped")


def main():
    """Main entry point for the streaming job"""
    import sys
    from config.settings import settings
    
    processor = FeatureProcessor(
        kafka_brokers=settings.kafka_brokers,
        postgres_url=settings.postgres_url,
        redis_url=settings.redis_url
    )
    
    try:
        processor.process_stream(topic=settings.kafka_topic)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        processor.stop()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in stream processing: {e}", exc_info=True)
        processor.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
