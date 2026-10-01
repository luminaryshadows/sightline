package com.privatesight.app.storage

import com.privatesight.app.analysis.DocumentAnalysis

/**
 * In-memory document store with explicit deletion — Kotlin port of ml/storage.py.
 *
 * Documents live only in this process. Nothing is written to durable storage,
 * and [deleteAll] returns the session to a clean state.
 */
class DocumentStore {

    data class Entry(
        val id: String,
        val analysis: DocumentAnalysis,
        val createdAt: Long = System.currentTimeMillis(),
    )

    private val entries = LinkedHashMap<String, Entry>()
    private var counter = 0

    @Synchronized
    fun add(analysis: DocumentAnalysis): String {
        counter++
        val id = "doc-$counter"
        entries[id] = Entry(id, analysis)
        return id
    }

    @Synchronized
    fun get(id: String): DocumentAnalysis? = entries[id]?.analysis

    @Synchronized
    fun delete(id: String): Boolean = entries.remove(id) != null

    @Synchronized
    fun deleteAll(): Int {
        val n = entries.size
        entries.clear()
        return n
    }

    @Synchronized
    fun count(): Int = entries.size

    @Synchronized
    fun ids(): List<String> = entries.keys.toList()
}
