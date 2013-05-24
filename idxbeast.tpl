<html>
    <head>
        <style type="text/css">
            #search_input
            {
                text-align:center;
            }
            img
            {
                margin: 20px;
            }
        </style>
    </head>
    <body>
        <div id=search_input>
            <div><img src="/idxbeast/images/idxbeast_small.jpg"></img></div>
            <div>
              <form name="search_form">
                <input name="q" type="text" size="50"/><input type="submit" value="Search"/>
              </form>
            </div>
        </div>
        <hr />
        <div id=search_results>
            % for id, type_, locator, relev, title in cursor:
            %     if type_ == 3:
                      <p><a href={{locator}}>{{locator}}</a><p>
            %     else:
                      <p><a href="/idxbeast?d={{id}}">{{locator}}</a></p>
            %     end
            % end
        </div>
    </body>
</html>

