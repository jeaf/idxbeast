#ifndef IDXLIB_H
#define IDXLIB_H

#include <string>
#include <unordered_map>

#include "charmap.h"
#include "db.h"

namespace idxb { namespace core {

    // The counts that describe how a specific word matches a document
    struct WordCounts
    {
        // How many times does the word appear in the doc?
        int64_t count;  

        // The sum of the "positions" of a word in a doc. e.g., for the following
        // text: "gamma abc def ghi abc", abc would have a totpos of 5, since if
        // appears at position 1 and at position 4. This value will be used to
        // compute the average pos, which is used for computing the relevance of
        // matches.
        int64_t totpos;
    };

    class Index
    {
    public:
        Index(std::shared_ptr<idxb::db::Connection> i_conn);

        void commit();
        void index_file(std::string path);
        void search(std::string word);

    private:

        template <typename Iterator>
        void index_blocks(int64_t docid, Iterator blocks_it, Iterator blocks_it_end)
        {
            std::string cur_word;
            int    cur_word_pos = 0;
            for (; blocks_it != blocks_it_end; ++blocks_it)
            {
                auto char_it     = blocks_it->cbegin();
                auto char_it_end = blocks_it->cend();

                while (char_it != char_it_end)
                {
                    // Process current word
                    while (char_it != char_it_end &&
                           *charmap[static_cast<uint8_t>(*char_it)])
                    {
                        cur_word += charmap[static_cast<uint8_t>(*char_it)];
                        ++char_it;
                    }

                    // Store current word
                    if (char_it != char_it_end && !cur_word.empty())
                    {
                        if (cur_word.size() > 1)
                        {
                            words[cur_word][docid].count++;
                            words[cur_word][docid].totpos += cur_word_pos;
                        }
                        ++cur_word_pos;
                        cur_word.clear();
                    }

                    // Advance until non-blank char
                    while (char_it != char_it_end &&
                           !*charmap[static_cast<uint8_t>(*char_it)]) ++char_it;
                }
            }

            // After reading all the blocks, store the last word
            if (cur_word.size() > 1)
            {
                words[cur_word][docid].count++;
                words[cur_word][docid].totpos += cur_word_pos;
            }
        }

        void        create_tables();
        int64_t     lookup_word(std::string word);
        std::string build_path(int64_t doc_path_id);
        int64_t     lookup_doc_path(std::string path);
        int64_t     lookup_doc_file(int64_t path_id);

        // The DB connection
        std::shared_ptr<idxb::db::Connection> conn;

        // The main index, stores the docid and counts for each word
        std::unordered_map<std::string, std::unordered_map<int64_t, WordCounts>> words;
    };

}}

#endif

