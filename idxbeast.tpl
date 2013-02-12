<html>
  <head>
    <style type="text/css">
    </style>
  </head>
  <body>
    <div><img src="/idxbeast/images/idxbeast.jpg"></img></div>
    <div>
      <form name="search_form">
        Query: <input type="text" name="q"/><input type="submit" value="Search"/>
      </form>
      <div>
        % for locator, relev, title, title_only in cursor:
          <p>{{locator}}</p>
        % end
      </div>
    </div>
  </body>
</html>

