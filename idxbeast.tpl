<html>
  <head>
    <style type="text/css">
    </style>
  </head>
  <body>
    <script src="/jquery.js"></script>
    <script src="/jquery.cookie.js"></script>
    <script src="/jquery.encoding.digests.sha1.js"></script>
    <script>
      $(document).ready(function()
      {
        var update_page = function(resp)
        {
          $('#search_results').html('')
          for (v in resp['res'])
          {
            var d = resp['res'][v]
            $('#search_results').append('<p><a href="/idxbeast/api/activate?doc_id=' + d.id + '">' + d.title + '</a></p>');
          }
          $('#search_results a').live('click', function()
          {
            $.getJSON($(this).attr('href'));
            return false;
          });
        };
        $('#btn_search_submit').click(function()
        {
          $.getJSON('/idxbeast/api/search', {'q': $('#inp_query').val()}, update_page)
          return false
        });
        $('#btn_login_submit').click(function()
        {
          var pwd = $('#inp_password').val()
          var pwd_hash = $.encoding.digests.hexSha1Str(pwd).toLowerCase();
          var sid = $.cookie('sid')
          var auth     = $.encoding.digests.hexSha1Str(pwd_hash + sid).toLowerCase()
          var loc_str = '/idxbeast?user=' + $('#inp_username').val() + '&auth=' + auth
          window.location = loc_str
          return false
        });
      });
    </script>
    <div>
      %if page == 'search':
        <a href="/idxbeast/logout">Logout</a>
        <form name="search_form">
          Query: <input id="inp_query" type="text" name="query"/>
          <input id="btn_search_submit" type="submit" value="Search"/>
        </form>
        <div id="search_results">
        </div>
      %elif page == 'login':
        <form name="login_form">
          Username: <input id="inp_username" type="text" name="username"/><br/>
          Password: <input id="inp_password" type="password" name="password"/>
          <input id="btn_login_submit" type="submit" value="Login"/>
        </form>
      %end
    </div>
  </body>
</html>

