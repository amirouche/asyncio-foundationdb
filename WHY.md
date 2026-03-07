# Why I Built This

Every layer you add is a tax on understanding.

One afternoon I spent three hours debugging a data problem. Two of those hours were in layers I didn't write, didn't own, and couldn't fully read. I dug through three pages of ORM traceback — the kind where every frame is a different abstraction and none of them are yours — to find the actual SQL query being generated, only to discover the fix required passing a raw SQL string back into Python. The escape hatch from the abstraction was the abstraction's own language. I had left Python, passed through the ORM, arrived at SQL, and the solution was to bring SQL back into Python wrapped in a string. The round trip had cost me hours and taught me nothing I could use the next time.

That afternoon is this library.

The standard Python web stack is obese — not in code, but in the knowledge required to operate it. SQL, the ORM's abstraction over SQL, the migration tool's abstraction over the schema, the query planner's model of your indices. Each layer requires specialist knowledge to debug and specialist knowledge to tune. Most of that knowledge has nothing to do with your actual domain. You pay it every time something breaks.

There is a different way. An ordered key-value store is a programmable storage system — what LISP is to programming languages. You don't learn a new storage paradigm every time you face a new problem. You build the storage that fits your problem, in the language you already speak, with the tools you already understand. You use your existing knowledge differently, not more of it.

That is what `asyncio-foundationdb` is built on.

## The Hidden Power Structure

Here is something the "just use Postgres" crowd rarely says out loud: the standard web stack — Python on top, SQL underneath, an ORM in between — is not just a technical choice. It is a power structure.

It creates specialists. The DBA who owns the schema. The backend developer who knows which ORM incantations produce acceptable query plans. The implicit rule that certain bugs require a different person, with a different context, speaking a different language. On a small team, those roles often collapse into one exhausted person. On a solo project, that person is you.

This is not dramatic. It shapes what you build, and what you don't. When debugging a data issue means switching from Python to SQL to PL/pgSQL to reading Postgres internals documentation, the friction is not neutral. It discourages you from going deep. It encourages you to paper over things. It makes your own application feel foreign to you.

That friction is a choice. And you can make a different one.

## One Language, All the Way Down

`asyncio-foundationdb` is built on a simple belief: your data layer should live in the same language as the rest of your application, expressed with the same tools, debuggable with the same skills.

FoundationDB gives you a remarkable foundation for this. It is a distributed database with real ACID transactions, ordered key-value storage, and a path from a single box to a resilient production cluster — without changing your data model. What it does not give you is opinions about how your domain should look. That is intentional. That is the point.

On top of FoundationDB, this library gives you building blocks: a tuple store with pattern-matching queries, a blob store, an entity-attribute-value store, an inverted index, a versioned knowledge graph. They are not an ORM. They do not pretend to know your domain. They are tools for building a data layer that is genuinely yours — in Python, readable by anyone on your team who knows Python, debuggable without a specialist on call.

You will not learn new algorithms or new data structures. You will use your existing knowledge differently. You choose your domain model. You express it in your language. You know exactly where the complexity lives, because you put it there.

## The Poison You Choose

Every API is a constraint. Every abstraction hides something. This is not a claim otherwise.

What it is claiming is that there is a difference between a constraint you have chosen, in a language you already speak, in a codebase you already own — and a constraint that lives somewhere else, documented in fragments across three different projects, triggered by an interaction between your ORM version and your database minor version, requiring someone else to diagnose.

With `asyncio-foundationdb`, the complexity is visible. It is in `found`. You can read it. You can fork it. When something breaks, the stack trace is in Python, the fix is in Python, and the person who can help you is anyone who knows Python.

On a small team, that is the difference between a bug that costs an hour and a bug that costs a week and a specialist.

## Who This Is For

This library is for people who have been burned. By the ORM that silently generated the wrong query. By the migration that worked in development and failed in production for reasons that required reading SQLAlchemy source code to understand. By the framework that made the first week easy and the second year hard.

It is for small teams who cannot afford to have their data layer be a black box. For solo developers who want to own the full stack without hiring themselves a DBA. For anyone who has felt that specific exhaustion of debugging something in a layer of your application that does not feel like yours.

You do not need a big team to use serious database technology. You do not need to accept the impedance mismatch as a fact of life. You do not need to learn three languages to build one application.

You just need a solid foundation, and the tools to build on it yourself.

---

*Questions, pushback, workarounds: [amirouche.boubekki@gmail.com](mailto:amirouche.boubekki@gmail.com)*
