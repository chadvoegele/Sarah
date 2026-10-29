# Historical code3 third-party material

The MIT grant in LICENSE applies only to owner-controlled material, not third-party
components. Existing repository notices and code8 covered-source/release documents
must be retained; this code3 note does not supersede them.

- `gradlew`: original authors, Copyright 2015–2021, Apache-2.0; original header retained.
- `gradle/wrapper/gradle-wrapper.jar`: Gradle wrapper; original embedded
  `META-INF/LICENSE` retained byte-for-byte. Its Apache-2.0 license is also copied to
  `CODE3-GRADLE-APACHE-2.0.txt`. No wrapper classes were modified.
- Android/Kotlin/AndroidX/OkHttp/coroutines/JUnit and test dependencies are declared,
  not vendored here. See THIRD-PARTY-NOTICES.md for the historical direct inventory and its
  explicit preliminary/unreviewed transitive-license boundary.
- `org.json:json:20240303` is a historical test-only dependency under the JSON.org
  license (including its “Good, not Evil” condition). It is not MIT or OSI-approved;
  no dependency JAR or copied org.json implementation is bundled in this source tree.
- Launcher artwork publication is owner-approved. Original artwork includes intact
  C2PA generated-media provenance/signatures; this is not third-party source code
  relicensed by the project. No claim of exclusivity over third-party marks is made.

No dependency resolution, license analyzer, build or test was run for publication.
