"""Preapproved WebFetch host table — verbatim port of CC preapproved.ts:14-131.

Security note: This list is ONLY for WebFetch (GET requests). The sandbox
system deliberately does NOT inherit this list for network restrictions, as
arbitrary network access to these domains could enable data exfiltration.

Item count: 89 string literals (CC source), 88 unique after frozenset dedup
(learn.microsoft.com appears twice in CC source — frozenset collapses to one).

Split at module load into HOSTNAME_ONLY + PATH_PREFIXES for O(1) lookup on the
common hostname-only case. Mirrors CC preapproved.ts:136-152.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Source list — verbatim from CC preapproved.ts:14-131
# ---------------------------------------------------------------------------

PREAPPROVED_HOSTS: frozenset[str] = frozenset(
    {
        # Anthropic
        "platform.claude.com",
        "code.claude.com",
        "modelcontextprotocol.io",
        "github.com/anthropics",
        "agentskills.io",
        # Top Programming Languages
        "docs.python.org",  # Python
        "en.cppreference.com",  # C/C++ reference
        "docs.oracle.com",  # Java
        "learn.microsoft.com",  # C#/.NET (also Azure — same host, frozenset deduplicates)
        "developer.mozilla.org",  # JavaScript/Web APIs (MDN)
        "go.dev",  # Go
        "pkg.go.dev",  # Go docs
        "www.php.net",  # PHP
        "docs.swift.org",  # Swift
        "kotlinlang.org",  # Kotlin
        "ruby-doc.org",  # Ruby
        "doc.rust-lang.org",  # Rust
        "www.typescriptlang.org",  # TypeScript
        # Web & JavaScript Frameworks/Libraries
        "react.dev",  # React
        "angular.io",  # Angular
        "vuejs.org",  # Vue.js
        "nextjs.org",  # Next.js
        "expressjs.com",  # Express.js
        "nodejs.org",  # Node.js
        "bun.sh",  # Bun
        "jquery.com",  # jQuery
        "getbootstrap.com",  # Bootstrap
        "tailwindcss.com",  # Tailwind CSS
        "d3js.org",  # D3.js
        "threejs.org",  # Three.js
        "redux.js.org",  # Redux
        "webpack.js.org",  # Webpack
        "jestjs.io",  # Jest
        "reactrouter.com",  # React Router
        # Python Frameworks & Libraries
        "docs.djangoproject.com",  # Django
        "flask.palletsprojects.com",  # Flask
        "fastapi.tiangolo.com",  # FastAPI
        "pandas.pydata.org",  # Pandas
        "numpy.org",  # NumPy
        "www.tensorflow.org",  # TensorFlow
        "pytorch.org",  # PyTorch
        "scikit-learn.org",  # Scikit-learn
        "matplotlib.org",  # Matplotlib
        "requests.readthedocs.io",  # Requests
        "jupyter.org",  # Jupyter
        # PHP Frameworks
        "laravel.com",  # Laravel
        "symfony.com",  # Symfony
        "wordpress.org",  # WordPress
        # Java Frameworks & Libraries
        "docs.spring.io",  # Spring
        "hibernate.org",  # Hibernate
        "tomcat.apache.org",  # Tomcat
        "gradle.org",  # Gradle
        "maven.apache.org",  # Maven
        # .NET & C# Frameworks
        "asp.net",  # ASP.NET
        "dotnet.microsoft.com",  # .NET
        "nuget.org",  # NuGet
        "blazor.net",  # Blazor
        # Mobile Development
        "reactnative.dev",  # React Native
        "docs.flutter.dev",  # Flutter
        "developer.apple.com",  # iOS/macOS
        "developer.android.com",  # Android
        # Data Science & Machine Learning
        "keras.io",  # Keras
        "spark.apache.org",  # Apache Spark
        "huggingface.co",  # Hugging Face
        "www.kaggle.com",  # Kaggle
        # Databases
        "www.mongodb.com",  # MongoDB
        "redis.io",  # Redis
        "www.postgresql.org",  # PostgreSQL
        "dev.mysql.com",  # MySQL
        "www.sqlite.org",  # SQLite
        "graphql.org",  # GraphQL
        "prisma.io",  # Prisma
        # Cloud & DevOps
        "docs.aws.amazon.com",  # AWS
        "cloud.google.com",  # Google Cloud
        "kubernetes.io",  # Kubernetes
        "www.docker.com",  # Docker
        "www.terraform.io",  # Terraform
        "www.ansible.com",  # Ansible
        "vercel.com/docs",  # Vercel
        "docs.netlify.com",  # Netlify
        "devcenter.heroku.com",  # Heroku
        # Testing & Monitoring
        "cypress.io",  # Cypress
        "selenium.dev",  # Selenium
        # Game Development
        "docs.unity.com",  # Unity
        "docs.unrealengine.com",  # Unreal Engine
        # Other Essential Tools
        "git-scm.com",  # Git
        "nginx.org",  # Nginx
        "httpd.apache.org",  # Apache HTTP Server
    }
)


# ---------------------------------------------------------------------------
# Module-load split: O(1) lookup for hostname-only case
# Mirrors CC preapproved.ts:136-152
# ---------------------------------------------------------------------------


def _split_preapproved() -> tuple[frozenset[str], dict[str, tuple[str, ...]]]:
    """Split PREAPPROVED_HOSTS into hostname-only set and path-prefix dict."""
    hosts: set[str] = set()
    paths: dict[str, list[str]] = {}
    for entry in PREAPPROVED_HOSTS:
        slash = entry.find("/")
        if slash == -1:
            hosts.add(entry)
        else:
            host = entry[:slash]
            path = entry[slash:]
            paths.setdefault(host, []).append(path)
    return frozenset(hosts), {h: tuple(ps) for h, ps in paths.items()}


HOSTNAME_ONLY: frozenset[str]
PATH_PREFIXES: dict[str, tuple[str, ...]]
HOSTNAME_ONLY, PATH_PREFIXES = _split_preapproved()


# ---------------------------------------------------------------------------
# Public lookup function — CC isPreapprovedHost(hostname, pathname)
# ---------------------------------------------------------------------------


def is_preapproved_host(hostname: str, pathname: str) -> bool:
    """Return True if (hostname, pathname) is covered by the preapproved list.

    Mirrors CC preapproved.ts:154-165 exactly:
    - Hostname-only entries: any pathname is accepted.
    - Path-prefix entries: pathname must equal the prefix or start with
      ``prefix + "/"`` — enforcing path segment boundaries so that
      ``/anthropics`` does NOT match ``/anthropics-evil/malware``.

    Args:
        hostname: Lowercased hostname extracted from URL (no port).
        pathname: URL path component (starts with "/" or empty string).

    Returns:
        True if the (hostname, pathname) pair is preapproved.
    """
    if hostname in HOSTNAME_ONLY:
        return True
    prefixes = PATH_PREFIXES.get(hostname)
    if prefixes:
        for p in prefixes:
            # Enforce segment boundary: exact match OR prefix + "/" sub-path
            if pathname == p or pathname.startswith(p + "/"):
                return True
    return False
