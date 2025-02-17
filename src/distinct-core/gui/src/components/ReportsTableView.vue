<template>
  <div class="table-responsive mb-4">
    <table class="table">
      <thead>
        <tr>
          <th scope="col">ID</th>
          <th scope="col">Timestamp</th>
          <th scope="col">Type</th>
          <th scope="col">Hierarchy</th>
          <th scope="col">URL</th>
          <th scope="col">Content</th>
        </tr>
      </thead>
      <tbody>

        <tr v-for="report in reports" v-bind:key="report.id">
          <th scope="row">{{report.id}}</th>
          <td>{{report.val.timestamp}}</td>
          <td>{{report.key}}</td>
          <td>{{report.val.hierarchy}}</td>
          <td class="href">{{report.val.href}}</td>

          <!-- Report Content -->
          <td>
            <div v-for="(val, key) in this.filterVals(report.val)" v-bind:key="key" class="val">

              <!-- custom layout: html -->
              <span v-if="key == 'html'">
                <b>{{key}}</b>:
                <pre class="language-html"><code>{{this.beautifyHTML(val)}}</code></pre>
              </span>

              <!-- custom layout: data (data_type = object) -->
              <!-- <span v-else-if="key == 'data' && report.val['data_type'] == 'object'">
                <b>{{key}}</b>:
                <pre class="language-js"><code>{{this.beautifyJS(JSON.stringify(val))}}</code></pre>
              </span> -->

              <!-- custom layout: callback (of message event listener) -->
              <span v-else-if="key == 'callback' && report.key == 'addeventlistener' && report.val['type'] == 'message'">
                <b>{{key}}</b>:
                <pre class="language-js"><code>{{this.beautifyJS(val)}}</code></pre>
              </span>

              <!-- standard -->
              <span v-else>
                <b>{{key}}</b>: {{val}}
              </span>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import Prism from 'prismjs'
import beautify from 'js-beautify'
import 'prismjs/themes/prism.css'

export default {
  name: 'ReportsTableView',
  props: ['reports', 'prettyPrintHTML'],
  computed: {
    numReports: function() {
      return this.reports.length
    }
  },
  methods: {
    'filterVals': function(vals) {
      return Object.fromEntries(Object.entries(vals).filter(([key]) => {
        return (
          key !== 'timestamp'
          && key !== 'hierarchy'
          && key !== 'href'
          && key !== 'hrefparts'
        )
      }))
    },
    'beautifyHTML': function(html) {
      if (this.prettyPrintHTML) {
        return beautify.html(html, {
          "indent_size": 2,
          "indent_char": " ",
          "indent_with_tabs": false,
          "eol": "\n",
          "end_with_newline": false,
          "indent_level": 0,
          "preserve_newlines": true,
          "max_preserve_newlines": 10,
          "space_in_paren": false,
          "space_in_empty_paren": false,
          "jslint_happy": false,
          "space_after_anon_function": false,
          "space_after_named_function": false,
          "brace_style": "collapse",
          "unindent_chained_methods": false,
          "break_chained_methods": false,
          "keep_array_indentation": false,
          "unescape_strings": false,
          "wrap_line_length": 0,
          "e4x": false,
          "comma_first": false,
          "operator_position": "before-newline",
          "indent_empty_lines": false,
          "templating": ["auto"]
        })
      } else {
        return html
      }
    },
    'beautifyJS': function(js) {
      if (this.prettyPrintHTML) {
        return beautify.js(js, {
          "indent_size": 2,
          "indent_char": " ",
          "indent_with_tabs": false,
          "eol": "\n",
          "end_with_newline": false,
          "indent_level": 0,
          "preserve_newlines": true,
          "max_preserve_newlines": 10,
          "space_in_paren": false,
          "space_in_empty_paren": false,
          "jslint_happy": false,
          "space_after_anon_function": false,
          "space_after_named_function": false,
          "brace_style": "collapse",
          "unindent_chained_methods": false,
          "break_chained_methods": false,
          "keep_array_indentation": false,
          "unescape_strings": false,
          "wrap_line_length": 0,
          "e4x": false,
          "comma_first": false,
          "operator_position": "before-newline",
          "indent_empty_lines": false,
          "templating": ["auto"]
        })
      } else {
        return js
      }
    }
  },
  updated() {
    console.log(this.$props.prettyPrintHTML)
    if (this.prettyPrintHTML) {
      Prism.highlightAll()
    }
  }
}
</script>

<style>
  pre {
    overflow: auto;
    max-height: 50vh;
    max-width: 80vw;
  }

  .val {
    overflow: auto;
    max-height: 50vh;
    max-width: 80vw;
  }

  .href {
    overflow: auto;
    max-width: 30vw;
  }
</style>
