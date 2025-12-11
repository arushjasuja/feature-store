from setuptools import setup, find_packages

setup(
    name="feature-store",
    version="1.0.0",
    description="Production ML Feature Store with real-time serving",
    author="Feature Store Team",
    author_email="team@example.com",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.11",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "pydantic==2.5.0",
        "pydantic-settings==2.1.0",
        "asyncpg==0.29.0",
        "redis[hiredis]==5.0.1",
        "msgpack==1.0.7",
        "kafka-python==2.0.2",
        "pyspark==3.4.1",
        "numpy==1.24.3",
        "prometheus-client==0.19.0",
        "python-json-logger==2.0.7",
        "httpx==0.25.2",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.3",
            "pytest-asyncio==0.21.1",
            "pytest-cov==4.1.0",
            "locust==2.19.1",
            "ipython==8.18.1",
            "black==23.12.1",
            "flake8==6.1.0",
            "mypy==1.7.1",
        ]
    },
    entry_points={
        "console_scripts": [
            "feature-store-api=api.main:main",
            "feature-store-init=scripts.init_db:main",
            "feature-store-seed=scripts.seed_data:main",
            "feature-store-bench=scripts.benchmark:main",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3.11",
    ],
)
